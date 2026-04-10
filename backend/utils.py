# backend/utils.py
# Handles PDF loading, text extraction, and chunk creation

import re
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter


def load_pdf(file_path: str):
    """
    Read a PDF file and extract text from each page.
    Returns: list of dicts with page_number and text
    """
    reader = PdfReader(file_path)
    pages = []

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({
                "page_number": page_num + 1,
                "text": text.strip()
            })

    return pages


def create_chunks(pages: list):
    """
    Split page text into overlapping chunks for embedding.
    Chunk size: 1000 characters, overlap: 200 characters
    Returns: list of dicts with chunk_id, chunk_text, page_number, preview
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )

    all_chunks = []
    chunk_id = 0

    for page in pages:
        chunks = splitter.split_text(page["text"])

        for chunk in chunks:
            all_chunks.append({
                "chunk_id": str(chunk_id),
                "chunk_text": chunk,
                "page_number": page["page_number"],
                "preview": chunk[:100] + "..."
            })
            chunk_id += 1

    return all_chunks


def get_pdf_info(file_path: str):
    """
    Extract basic metadata from a PDF file.
    Returns: dict with total_pages and file_path
    """
    reader = PdfReader(file_path)
    return {
        "total_pages": len(reader.pages),
        "file_path": file_path
    }


def sanitize_doc_id(filename: str) -> str:
    """
    Convert a filename into a valid ChromaDB collection name.
    Rules: alphanumeric + underscores only, min 3 chars, no consecutive underscores
    """
    doc_id = filename.replace(".pdf", "").replace(" ", "_").lower()
    doc_id = re.sub(r'[^a-z0-9_-]', '', doc_id)
    doc_id = re.sub(r'_+', '_', doc_id)
    doc_id = doc_id.strip('_')
    if len(doc_id) < 3:
        doc_id = "doc_" + doc_id
    return doc_id