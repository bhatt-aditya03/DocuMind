import os
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
import chromadb
from chromadb.config import Settings

load_dotenv()


def get_embeddings():
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )
    return embeddings


def get_chroma_client():
    client = chromadb.PersistentClient(path="./chroma_db")
    return client


def store_chunks(chunks: list, doc_id: str):
    embeddings_model = get_embeddings()
    client = get_chroma_client()

    try:
        client.delete_collection(name=doc_id)
    except:
        pass

    collection = client.create_collection(name=doc_id)

    texts = [chunk["chunk_text"] for chunk in chunks]
    ids = [chunk["chunk_id"] for chunk in chunks]
    metadatas = [
        {
            "page_number": chunk["page_number"],
            "preview": chunk["preview"]
        }
        for chunk in chunks
    ]

    vectors = embeddings_model.embed_documents(texts)

    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=metadatas
    )

    print(f"✅ {len(chunks)} chunks stored in ChromaDB!")
    return collection


def search_chunks(question: str, doc_id: str, top_k: int = 3):
    embeddings_model = get_embeddings()
    client = get_chroma_client()

    collection = client.get_collection(name=doc_id)

    question_vector = embeddings_model.embed_query(question)

    results = collection.query(
        query_embeddings=[question_vector],
        n_results=top_k
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "page_number": results["metadatas"][0][i]["page_number"],
            "preview": results["metadatas"][0][i]["preview"]
        })

    return chunks


def generate_answer(question: str, context_chunks: list):
    groq_api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=groq_api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    context = ""
    for i, chunk in enumerate(context_chunks):
        context += f"\n[Page {chunk['page_number']}]: {chunk['text']}\n"

    system_prompt = """You are a document analysis assistant.
STRICT RULES:
1. Answer ONLY using the provided context
2. If the answer is not in the context, say exactly: "I cannot find this information in the document."
3. Always mention the page number where you found the answer
4. Be concise and accurate"""

    user_message = f"""Context from document:
{context}

Question: {question}

Answer based only on the context above:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]

    response = llm.invoke(messages)

    answer_text = response.content
    if "cannot find" in answer_text.lower():
        confidence = "low"
    else:
        confidence = "high"

    return {
        "answer": answer_text,
        "confidence": confidence,
        "sources": context_chunks
    }