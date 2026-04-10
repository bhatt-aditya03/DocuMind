# backend/rag_pipeline.py
# Core RAG pipeline — embeddings, vector storage, similarity search, and LLM answer generation

import os
from functools import lru_cache
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
import chromadb

load_dotenv()


def get_api_key() -> str:
    """
    Retrieve Groq API key from Streamlit secrets or environment variable.
    """
    try:
        import streamlit as st
        return st.secrets["GROQ_API_KEY"]
    except (ImportError, KeyError):
        return os.getenv("GROQ_API_KEY")


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Load HuggingFace embedding model once and cache it.
    Avoids reloading the model on every function call.
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )


@lru_cache(maxsize=1)
def get_chroma_client():
    """
    Initialize ChromaDB persistent client once and cache it.
    """
    return chromadb.PersistentClient(path="./chroma_db")


def store_chunks(chunks: list, doc_id: str):
    """
    Embed chunks using HuggingFace and store them in ChromaDB.
    Deletes existing collection for the same doc_id before storing.
    """
    embeddings_model = get_embeddings()
    client = get_chroma_client()

    # Delete existing collection if it exists
    try:
        client.delete_collection(name=doc_id)
    except Exception:
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
    """
    Find the most relevant chunks for a given question using similarity search.
    Returns: list of dicts with text, page_number, and preview
    """
    embeddings_model = get_embeddings()
    client = get_chroma_client()

    try:
        collection = client.get_collection(name=doc_id)
    except Exception as e:
        raise ValueError(f"Document '{doc_id}' not found in ChromaDB. Please upload the PDF first.") from e

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
    """
    Generate an answer using Groq LLaMA3 based strictly on retrieved context chunks.
    Returns: dict with answer, confidence level, and source chunks
    """
    llm = ChatGroq(
        api_key=get_api_key(),
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    context = ""
    for chunk in context_chunks:
        context += f"\n[Page {chunk['page_number']}]: {chunk['text']}\n"

    system_prompt = """You are a helpful document analysis assistant.
STRICT RULES:
1. Answer ONLY using the provided context chunks
2. Read ALL context chunks carefully before answering
3. Even if information is spread across multiple chunks, combine them for a complete answer
4. Always mention page numbers where you found the answer like (Page X)
5. If and ONLY IF the answer is truly not present anywhere in the context, say: "I cannot find this information in the document."
6. Be specific and detailed in your answers"""

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

    confidence = "low" if "cannot find" in answer_text.lower() else "high"

    return {
        "answer": answer_text,
        "confidence": confidence,
        "sources": context_chunks
    }