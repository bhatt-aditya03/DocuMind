import streamlit as st
import requests

st.set_page_config(
    page_title="DocuMind — AI Document Analyzer",
    page_icon="🧠",
    layout="wide"
)

BACKEND_URL = "http://127.0.0.1:8000"

if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "filename" not in st.session_state:
    st.session_state.filename = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.markdown("<h1 style='text-align: center;'>🧠 DocuMind</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>AI-Powered Legal & Research Document Analyzer</p>", unsafe_allow_html=True)
st.divider()
col1, col2 = st.columns([1, 2])

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
                try:
                    files = {"file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        "application/pdf"
                    )}
                    response = requests.post(
                        f"{BACKEND_URL}/upload", files=files
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.doc_id = data["doc_id"]
                        st.session_state.filename = uploaded_file.name
                        st.session_state.chat_history = []

                        st.success("✅ PDF Successfully Processed!")

                        col_a, col_b = st.columns(2)
                        col_a.metric("📄 Pages", data["total_pages"])
                        col_b.metric("🧩 Chunks", data["total_chunks"])

                        with st.spinner("📝 Generating summary..."):
                            sum_resp = requests.get(
                                f"{BACKEND_URL}/summary/{data['doc_id']}"
                            )
                            if sum_resp.status_code == 200:
                                st.session_state.summary = \
                                    sum_resp.json()["summary"]
                    else:
                        st.error(f"❌ {response.json()['detail']}")

                except Exception as e:
                    st.error(f"❌ Backend error: {str(e)}")

    if st.session_state.summary:
        st.divider()
        st.subheader("📋 Document Summary")
        st.info(st.session_state.summary)

with col2:
    st.subheader("💬 Ask Questions")

    if st.session_state.doc_id is None:
        st.warning("👈 Please upload a PDF first!")
    else:
        st.success(f"📄 Active: **{st.session_state.filename}**")

        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat["question"])

            with st.chat_message("assistant"):
                # Confidence
                if chat["confidence"] == "high":
                    st.success("🟢 High Confidence")
                else:
                    st.error("🔴 Low Confidence — Answer may not be in document")

                st.write(chat["answer"])

                if chat["confidence"] == "high" and chat["sources"]:
                    st.markdown("**📌 Sources Used:**")
                    for src in chat["sources"]:
                        with st.expander(f"📄 Page {src['page_number']}"):
                            st.caption(src["preview"])

                st.divider()

        question = st.chat_input(
            "Ask anything about the document..."
        )

        if question:
            with st.spinner("🤔 Analyzing document..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/ask",
                        json={
                            "question": question,
                            "doc_id": st.session_state.doc_id
                        }
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.chat_history.append({
                            "question": question,
                            "answer": data["answer"],
                            "confidence": data["confidence"],
                            "sources": data["sources"]
                        })
                        st.rerun()
                    else:
                        st.error(f"❌ {response.json()['detail']}")

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()