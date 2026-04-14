# backend/summarizer.py
# Generates a structured summary of a document using Groq LLaMA3

import os
from backend.utils import get_api_key
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

def generate_summary(chunks: list):
    """
    Generate a structured document summary using the first 10 chunks.
    Analyzes document type, main topic, key points, and important sections.
    Returns: dict with summary text, chunks_analyzed, and total_chunks
    """
    llm = ChatGroq(
        api_key=get_api_key(),
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    # Use first 10 chunks for summary — covers document overview
    top_chunks = chunks[:10]

    context = ""
    for chunk in top_chunks:
        context += f"\n[Page {chunk['page_number']}]: {chunk['chunk_text']}\n"

    system_prompt = """You are a document summarization assistant.
Your job is to create a clear, concise summary of the document.
Structure your summary as:
1. Document Type (what kind of document is this)
2. Main Topic (what is this document about)
3. Key Points (3-5 most important points)
4. Important Sections (main sections or chapters)
Keep the summary under 200 words."""

    user_message = f"""Here are excerpts from the document:
{context}

Please provide a structured summary of this document:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]

    response = llm.invoke(messages)

    return {
        "summary": response.content,
        "chunks_analyzed": len(top_chunks),
        "total_chunks": len(chunks)
    }