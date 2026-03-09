from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def load_pdf(file_path: str):
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
    reader = PdfReader(file_path)
    return {
        "total_pages": len(reader.pages),
        "file_path": file_path
    }