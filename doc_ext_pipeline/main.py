import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import shutil
import uuid
import numpy as np
from deepface import DeepFace

from preprocessor import process_pdf

app = FastAPI(title="Face Extraction & Verification API")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "processed_output"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def clean_value(v):
    """
    Convert numpy types → Python native types so JSON encoding never fails.
    """
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.ndarray, list, tuple)):
        return [clean_value(x) for x in v]
    if isinstance(v, dict):
        return {k: clean_value(v) for k, v in v.items()}
    return v

@app.post("/extract-faces")
async def extract_faces(pdf: UploadFile = File(...)):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    file_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{file_id}.pdf"

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(pdf.file, buffer)

    try:
        result = process_pdf(str(saved_path), output_dir=str(OUTPUT_DIR))
        return JSONResponse({
            "status": "success",
            "pdf": pdf.filename,
            "result": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face extraction failed: {e}")

@app.post("/verify-faces")
async def verify_faces(
        img1: UploadFile = File(...),
        img2: UploadFile = File(...)
):
    img1_path = UPLOAD_DIR / f"{uuid.uuid4()}_{img1.filename}"
    img2_path = UPLOAD_DIR / f"{uuid.uuid4()}_{img2.filename}"

    with open(img1_path, "wb") as f:
        shutil.copyfileobj(img1.file, f)

    with open(img2_path, "wb") as f:
        shutil.copyfileobj(img2.file, f)

    try:
        result = DeepFace.verify(
            img1_path=str(img1_path),
            img2_path=str(img2_path),
            detector_backend="mtcnn",
            enforce_detection=False
        )

        # CLEAN RESULT FOR JSON SAFETY
        cleaned = clean_value(result)

        return cleaned

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face verification failed: {e}")

    finally:
        try:
            os.remove(img1_path)
            os.remove(img2_path)
        except:
            pass


@app.get("/")
def root():
    return {"message": "Face Extraction + Verification API Ready!"}
