# frontend/app.py
# Streamlit UI — DocuMind document analyzer interface

import streamlit as st
import sys
import os
import tempfile

# Add project root to path for backend imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import load_pdf, create_chunks, get_pdf_info, sanitize_doc_id
from backend.rag_pipeline import store_chunks, search_chunks, generate_answer
from backend.summarizer import generate_summary

st.set_page_config(
    page_title="DocuMind — AI Document Analyzer",
    page_icon="🧠",
    layout="wide"
)

# ─── Session State ─────────────────────────────────────────────
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "filename" not in st.session_state:
    st.session_state.filename = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ─── Header ────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align: center;'>🧠 DocuMind</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align: center; color: gray;'>AI-Powered Legal & Research Document Analyzer</p>",
    unsafe_allow_html=True
)
st.divider()

col1, col2 = st.columns([1, 2])

# ════════════════════════════════════════
# LEFT COLUMN — Upload + Summary
# ════════════════════════════════════════
with col1:
    st.subheader("📄 Upload Document")

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Legal contracts, research papers, any PDF!"
    )

    if uploaded_file is not None:
        if st.session_state.filename != uploaded_file.name:
            with st.spinner("🔄 Processing PDF..."):
                tmp_path = None
                try:
                    # Write to temp file safely — always cleaned up
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".pdf"
                    ) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    # Validate PDF has extractable text
                    info = get_pdf_info(tmp_path)
                    pages = load_pdf(tmp_path)

                    if not pages:
                        st.error(
                            "No extractable text found in this PDF. "
                            "The file may be scanned or image-based."
                        )
                    else:
                        chunks = create_chunks(pages)
                        doc_id = sanitize_doc_id(uploaded_file.name)

                        store_chunks(chunks, doc_id=doc_id)

                        st.session_state.doc_id = doc_id
                        st.session_state.filename = uploaded_file.name
                        st.session_state.chat_history = []

                        st.success("✅ PDF Successfully Processed!")

                        col_a, col_b = st.columns(2)
                        col_a.metric("📄 Pages", info["total_pages"])
                        col_b.metric("🧩 Chunks", len(chunks))

                        # Auto summary
                        with st.spinner("📝 Generating summary..."):
                            result = generate_summary(chunks)
                            st.session_state.summary = result["summary"]

                except Exception as e:
                    st.error(f"Failed to process PDF: {str(e)}")

                finally:
                    # Always clean up temp file
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

    # Summary display
    if st.session_state.summary:
        st.divider()
        st.subheader("📋 Document Summary")
        st.info(st.session_state.summary)

# ════════════════════════════════════════
# RIGHT COLUMN — Chat Interface
# ════════════════════════════════════════
with col2:
    st.subheader("💬 Ask Questions")

    if st.session_state.doc_id is None:
        st.warning("👈 Please upload a PDF first!")
    else:
        st.success(f"📄 Active: **{st.session_state.filename}**")

        # Chat history
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat["question"])

            with st.chat_message("assistant"):
                if chat["confidence"] == "high":
                    st.success("🟢 High Confidence")
                else:
                    st.error("🔴 Low Confidence")

                st.write(chat["answer"])

                if chat["confidence"] == "high" and chat["sources"]:
                    st.markdown("**📌 Sources Used:**")
                    for src in chat["sources"]:
                        with st.expander(f"📄 Page {src['page_number']}"):
                            st.caption(src["preview"])

                st.divider()

        # Question input
        question = st.chat_input("Ask anything about the document...")

        if question:
            with st.spinner("🤔 Analyzing document..."):
                try:
                    context_chunks = search_chunks(
                        question=question,
                        doc_id=st.session_state.doc_id,
                        top_k=3
                    )
                    result = generate_answer(
                        question=question,
                        context_chunks=context_chunks
                    )

                    st.session_state.chat_history.append({
                        "question": question,
                        "answer": result["answer"],
                        "confidence": result["confidence"],
                        "sources": result["sources"]
                    })
                    st.rerun()

                except ValueError as e:
                    st.error(f"Document error: {str(e)}")
                except Exception as e:
                    st.error(f"Failed to generate answer: {str(e)}")

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()