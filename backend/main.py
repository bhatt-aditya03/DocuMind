import os
import re
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.utils import load_pdf, create_chunks, get_pdf_info
from backend.rag_pipeline import store_chunks, search_chunks, generate_answer
from backend.summarizer import generate_summary

load_dotenv()

app = FastAPI(
    title="DocuMind API",
    description="RAG-based Legal & Research Document Analyzer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

current_doc = {"doc_id": None, "filename": None, "total_chunks": 0}

class QuestionRequest(BaseModel):
    question: str
    doc_id: str

@app.get("/")
def root():
    return {
        "message": "Welcome to DocuMind API! 🧠",
        "status": "running",
        "endpoints": ["/upload", "/ask", "/summary/{doc_id}"]
    }

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    PDF file lo → chunks banao → ChromaDB mein store karo
    Returns: doc_id, total_pages, total_chunks
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sirf PDF files allowed hain!")

    try:
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        info = get_pdf_info(file_path)

        pages = load_pdf(file_path)

        chunks = create_chunks(pages)

        doc_id = file.filename.replace(".pdf", "").replace(" ", "_").lower()
        doc_id = re.sub(r'[^a-z0-9_-]', '', doc_id)
        doc_id = re.sub(r'_+', '_', doc_id)
        doc_id = doc_id.strip('_')
        if len(doc_id) < 3:
            doc_id = "doc_" + doc_id

        store_chunks(chunks, doc_id=doc_id)

        current_doc["doc_id"] = doc_id
        current_doc["filename"] = file.filename
        current_doc["total_chunks"] = len(chunks)

        return {
            "success": True,
            "message": f"PDF successfully processed!",
            "doc_id": doc_id,
            "filename": file.filename,
            "total_pages": info["total_pages"],
            "total_chunks": len(chunks)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """
    Question lo → similar chunks dhundho → Groq se answer generate karo
    Returns: answer, confidence, sources with page numbers
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question empty nahi ho sakta!")

    if not request.doc_id:
        raise HTTPException(status_code=400, detail="Pehle PDF upload karo!")

    try:
        context_chunks = search_chunks(
            question=request.question,
            doc_id=request.doc_id,
            top_k=3
        )

        result = generate_answer(
            question=request.question,
            context_chunks=context_chunks
        )

        return {
            "success": True,
            "question": request.question,
            "answer": result["answer"],
            "confidence": result["confidence"],
            "sources": [
                {
                    "page_number": src["page_number"],
                    "preview": src["preview"]
                }
                for src in result["sources"]
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/summary/{doc_id}")
async def get_summary(doc_id: str):
    """
    Document ka automatic summary do
    Returns: structured summary
    """
    try:
        from backend.rag_pipeline import get_chroma_client
        client = get_chroma_client()

        try:
            collection = client.get_collection(name=doc_id)
        except:
            raise HTTPException(
                status_code=404,
                detail="Document nahi mila! Pehle PDF upload karo."
            )

        data = collection.get()
        chunks = [
            {
                "chunk_text": doc,
                "page_number": meta["page_number"],
                "preview": meta["preview"]
            }
            for doc, meta in zip(data["documents"], data["metadatas"])
        ]

        result = generate_summary(chunks)

        return {
            "success": True,
            "doc_id": doc_id,
            "summary": result["summary"],
            "chunks_analyzed": result["chunks_analyzed"],
            "total_chunks": result["total_chunks"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")