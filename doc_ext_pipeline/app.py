# streamlit_app.py

import streamlit as st
import requests
from PIL import Image

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Face Extraction & Verification", layout="wide")
st.title("🧠 Face Extraction & Face Verification System")


# ================================================================
# 🟩 PDF FACE EXTRACTION
# ================================================================
st.header("📄 Extract Faces from PDF")

pdf_file = st.file_uploader("Upload a PDF", type=["pdf"], key="pdf_upload")

if st.button("Extract Faces") and pdf_file:
    with st.spinner("Processing PDF..."):
        files = {"pdf": (pdf_file.name, pdf_file, "application/pdf")}
        response = requests.post(f"{BACKEND_URL}/extract-faces", files=files)

    if response.status_code != 200:
        st.error("Error: " + response.text)
    else:
        result = response.json()
        st.success("Face extraction completed!")

        st.subheader("🔍 Extraction Summary")
        st.json(result)

        pages = list(result["result"].values())[0]

        st.subheader("📘 Annotated Pages (Detection Boxes)")
        for page in pages:
            if page.get("annotated_page"):
                st.image(page["annotated_page"], caption=f"Annotated Page {page['page']}",
                         use_column_width=True)

        st.subheader("🖼 Cropped Faces")
        for page in pages:
            for face in page["faces"]:
                if face.get("crop"):
                    st.image(face["crop"], width=200)


# ================================================================
# 🟦 FACE VERIFICATION
# ================================================================
st.header("🧑‍🤝‍🧑 Face Verification")

col1, col2 = st.columns(2)

with col1:
    img1 = st.file_uploader("Upload First Face Image", type=["jpg", "jpeg", "png"])

with col2:
    img2 = st.file_uploader("Upload Second Face Image", type=["jpg", "jpeg", "png"])

if st.button("Verify Faces"):
    if not img1 or not img2:
        st.warning("Upload both images.")
    else:
        files = {
            "img1": (img1.name, img1, "image/jpeg"),
            "img2": (img2.name, img2, "image/jpeg"),
        }

        with st.spinner("Comparing..."):
            response = requests.post(f"{BACKEND_URL}/verify-faces", files=files)

        if response.status_code != 200:
            st.error("Error: " + response.text)
        else:
            result = response.json()

            st.subheader("🔍 Verification Results")
            st.json(result)

            colA, colB = st.columns(2)
            colA.image(img1, caption="Image 1", width=250)
            colB.image(img2, caption="Image 2", width=250)

            if result["verified"]:
                st.success("✅ Faces MATCH")
            else:
                st.error("❌ Faces DO NOT MATCH")


st.markdown("""
---
### 💡 Tips
- Make sure backend is running before using Streamlit.
- Clear face images improve accuracy.
- Large PDFs may take time for analysis.
""")
