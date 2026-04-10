# backend/main.py
# FastAPI server — exposes RAG pipeline as REST API endpoints

import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.utils import load_pdf, create_chunks, get_pdf_info, sanitize_doc_id
from backend.rag_pipeline import store_chunks, search_chunks, generate_answer
from backend.summarizer import generate_summary

load_dotenv()

# ─── FastAPI App ───────────────────────────────────────────────
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


# ─── Request Models ────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str
    doc_id: str


# ─── Root Endpoint ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": "Welcome to DocuMind API!",
        "status": "running",
        "endpoints": ["/upload", "/ask", "/summary/{doc_id}"]
    }


# ─── Upload Endpoint ───────────────────────────────────────────
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Accept a PDF file, process it into chunks, and store in ChromaDB.
    Returns doc_id, total_pages, and total_chunks.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    tmp_path = None
    try:
        # Write uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name

        info = get_pdf_info(tmp_path)
        pages = load_pdf(tmp_path)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in the PDF. The file may be scanned or image-based."
            )

        chunks = create_chunks(pages)
        doc_id = sanitize_doc_id(file.filename)
        store_chunks(chunks, doc_id=doc_id)

        return {
            "success": True,
            "message": "PDF successfully processed.",
            "doc_id": doc_id,
            "filename": file.filename,
            "total_pages": info["total_pages"],
            "total_chunks": len(chunks)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )
    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ─── Ask Endpoint ──────────────────────────────────────────────
@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """
    Accept a question and doc_id, retrieve relevant chunks,
    and return an LLM-generated answer with page citations.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    if not request.doc_id:
        raise HTTPException(
            status_code=400,
            detail="doc_id is required. Please upload a PDF first."
        )

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

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate answer: {str(e)}"
        )


# ─── Summary Endpoint ──────────────────────────────────────────
@app.get("/summary/{doc_id}")
async def get_summary(doc_id: str):
    """
    Retrieve and summarize a previously uploaded document by doc_id.
    """
    try:
        from backend.rag_pipeline import get_chroma_client
        client = get_chroma_client()

        try:
            collection = client.get_collection(name=doc_id)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail="Document not found. Please upload the PDF first."
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )