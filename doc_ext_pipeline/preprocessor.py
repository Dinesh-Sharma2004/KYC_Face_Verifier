import os
import argparse
import multiprocessing
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
import torch
from facenet_pytorch import MTCNN
from tqdm import tqdm
from deepface import DeepFace

torch.set_num_threads(1)


def analyze_face(img):
    """Run DeepFace analysis on the cropped face."""
    try:
        result = DeepFace.analyze(
            img_path=np.array(img),
            actions=['age', 'gender', 'emotion', 'race'],
            enforce_detection=True,
            detector_backend='mtcnn',
            silent=True
        )

        if isinstance(result, list):
            result = result[0]

        return {
            "age": result.get("age"),
            "gender": result.get("dominant_gender"),
            "emotion": result.get("dominant_emotion"),
            "race": result.get("dominant_race")
        }

    except ValueError as e:
        if "Face could not be detected" in str(e):
            return None
        print(f"DeepFace ValueError: {e}")
        return None

    except Exception as e:
        print(f"DeepFace error: {e}")
        return None


def process_pdf(file_path, mtcnn=None, output_dir="./processed_output"):
    """
    Processes a PDF:
    - Detects faces
    - Saves face crops
    - Saves annotated page images
    - Returns structured results
    """

    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_subdir = output_dir / file_path.stem
    output_subdir.mkdir(parents=True, exist_ok=True)

    try:
        pdf = fitz.open(file_path)
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        return {str(file_path): f"skipped: {e}"}

    results = []

    # Initialize MTCNN if not passed
    if mtcnn is None:
        mtcnn = MTCNN(keep_all=True, device="cpu",
                      thresholds=[0.7, 0.8, 0.9], post_process=True)

    for page_index, page in enumerate(pdf, start=1):
        try:
            # Render page as image
            pix = page.get_pixmap(dpi=100)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Detect faces
            boxes, probs = mtcnn.detect(img)

            # Create an annotated copy of page
            annotated = img.copy()
            draw = ImageDraw.Draw(annotated)

            face_list = []

            if boxes is not None:
                for idx, box in enumerate(boxes):
                    x1, y1, x2, y2 = map(int, box)

                    # Skip very small boxes
                    if (x2 - x1) < 10 or (y2 - y1) < 10:
                        continue

                    # ---- SAVE CROP ----
                    crop = img.crop((x1, y1, x2, y2))
                    crop_path = output_subdir / f"page_{page_index}_face_{idx+1}.jpg"
                    crop.save(crop_path, quality=80)

                    # ---- DRAW BOUNDING BOX ----
                    draw.rectangle([x1, y1, x2, y2], outline="red", width=3)

                    # ---- ANALYZE FACE ----
                    analysis = analyze_face(crop)

                    face_list.append({
                        "coords": [x1, y1, x2, y2],
                        "crop": str(crop_path),
                        "analysis": analysis if analysis else "no_face_detected"
                    })

            # Save annotated page
            annotated_page_path = output_subdir / f"page_{page_index}_annotated.jpg"
            annotated.save(annotated_page_path, quality=90)

            results.append({
                "page": page_index,
                "faces_detected": len(face_list),
                "faces": face_list,
                "annotated_page": str(annotated_page_path)
            })

        except Exception as e:
            print(f"Error processing page {page_index}: {e}")
            results.append({
                "page": page_index,
                "error": str(e)
            })

    pdf.close()

    return {str(file_path): results}


def worker(file_path, output_dir):
    """Single-worker wrapper for process_pdf."""
    try:
        mtcnn = MTCNN(keep_all=True, device="cpu",
                      thresholds=[0.7, 0.8, 0.9], post_process=True)
        return process_pdf(file_path, mtcnn, output_dir)
    except Exception as e:
        print(f"Worker failed for {file_path}: {e}")
        return {str(file_path): f"error: {e}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", help="Folder containing PDFs")
    parser.add_argument("--output_dir", default="./processed_output")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [f for f in input_path.glob("**/*.pdf")]
    if not files:
        print(f"No PDFs found in {input_path}")
        return

    print(f"Found {len(files)} PDFs to process")
    print("Warming up DeepFace...")

    try:
        DeepFace.analyze(np.zeros((50, 50, 3)), actions=['age'],
                         enforce_detection=False, silent=True)
        print("DeepFace ready.")
    except Exception as e:
        print(f"Warning: DeepFace warmup failed: {e}")

    results = []
    start = time.time()

    if args.workers <= 1:
        for f in tqdm(files):
            results.append(worker(str(f), str(output_dir)))
    else:
        with multiprocessing.Pool(args.workers) as pool:
            tasks = [pool.apply_async(worker, (str(f), str(output_dir))) for f in files]
            for t in tqdm(tasks):
                results.append(t.get())

    end = time.time()
    print(f"Completed in {end - start:.2f}s")

    for res in results:
        print(res)


if __name__ == "__main__":
    main()
