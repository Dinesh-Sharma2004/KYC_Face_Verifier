#!/usr/bin/env python3
"""
pdf_face_analyze.py

Scan PDFs, detect faces with MTCNN, analyze with DeepFace, and write per-PDF JSON results.

Usage:
    python pdf_face_analyze.py /path/to/pdfs --output_dir ./processed_output --workers 2 --dpi 150
"""

import os
import argparse
import multiprocessing as mp
from pathlib import Path
import time
import json
import logging
from typing import List, Dict, Any, Optional

import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import torch
from facenet_pytorch import MTCNN
from tqdm import tqdm
from deepface import DeepFace

# Limit CPU threads per process for deterministic CPU usage
torch.set_num_threads(1)

# Globals populated in worker processes
_WORKER_MTCNN = None

logger = logging.getLogger("pdf_face_analyzer")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)


def analyze_face(img: Image.Image, upscale_small: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Run DeepFace.analyze on a PIL Image (RGB). Returns analysis dict or None if no face detected.
    upscale_small: if provided and face crop has any dimension < threshold, upscale by factor.
    """
    try:
        arr = np.array(img)
        # DeepFace wants BGR sometimes; but DeepFace handles numpy arrays as RGB generally —
        # keep as is and set enforce_detection True; if fails, try enforce_detection=False fallback.
        res = DeepFace.analyze(
            img_path=arr,
            actions=['age', 'gender', 'emotion', 'race'],
            enforce_detection=True,
            detector_backend='mtcnn',
            silent=True
        )
        if isinstance(res, list):
            res = res[0]
        return {
            "age": res.get("age"),
            "gender": res.get("dominant_gender"),
            "emotion": res.get("dominant_emotion"),
            "race": res.get("dominant_race")
        }
    except ValueError as e:
        # Face not detected with enforce_detection=True
        # Return None to indicate detection failure for this crop
        if "Face could not be detected" in str(e) or "face could not be detected" in str(e).lower():
            return None
        logger.warning(f"DeepFace ValueError (non-detection): {e}")
        return None
    except Exception as e:
        logger.exception(f"DeepFace error: {e}")
        # Try a relaxed fallback (enforce_detection=False) to get rough output if needed
        try:
            rf = DeepFace.analyze(
                img_path=np.array(img),
                actions=['age', 'gender', 'emotion', 'race'],
                enforce_detection=False,
                detector_backend='mtcnn',
                silent=True
            )
            if isinstance(rf, list):
                rf = rf[0]
            return {
                "age": rf.get("age"),
                "gender": rf.get("dominant_gender"),
                "emotion": rf.get("dominant_emotion"),
                "race": rf.get("dominant_race"),
                "note": "fallback_enforce_detection_false"
            }
        except Exception as e2:
            logger.exception(f"DeepFace fallback failed: {e2}")
            return None


def process_pdf(file_path: str, output_dir: str, dpi: int = 100, min_face_size: int = 10, upscale_small_faces: Optional[float] = None) -> Dict[str, Any]:
    """
    Detect faces on each page and analyze them. Returns a dict with structured results.
    Also writes a JSON file with the results to output_dir/<pdf_stem>.json and crops to output_dir/<pdf_stem>/
    """
    file_path = Path(file_path)
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)
    output_subdir = out_base / file_path.stem
    output_subdir.mkdir(parents=True, exist_ok=True)

    result_summary: Dict[str, Any] = {
        "file": str(file_path),
        "pages": [],
        "error": None,
        "processing_time_s": None
    }

    start_time = time.time()
    try:
        pdf = fitz.open(file_path)
    except Exception as e:
        logger.exception(f"Failed to open PDF {file_path}: {e}")
        result_summary["error"] = f"open_failed: {e}"
        result_summary["processing_time_s"] = round(time.time() - start_time, 2)
        return result_summary

    try:
        for page_idx, page in enumerate(pdf, start=1):
            page_entry: Dict[str, Any] = {"page": page_idx, "faces_detected": 0, "faces": []}
            try:
                pix = page.get_pixmap(dpi=dpi)
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert("RGB")
            except Exception as e:
                logger.warning(f"Page render failed for {file_path} page {page_idx}: {e}")
                page_entry["error"] = f"render_failed: {e}"
                result_summary["pages"].append(page_entry)
                continue

            try:
                # Use shared MTCNN in worker process
                global _WORKER_MTCNN
                if _WORKER_MTCNN is None:
                    # fallback: initialize locally if somehow worker init didn't run
                    _WORKER_MTCNN = MTCNN(keep_all=True, device="cpu", thresholds=[0.7, 0.8, 0.9], post_process=True)

                boxes, probs = _WORKER_MTCNN.detect(img)
            except Exception as e:
                logger.exception(f"MTCNN detection failed for {file_path} page {page_idx}: {e}")
                page_entry["error"] = f"mtcnn_failed: {e}"
                result_summary["pages"].append(page_entry)
                continue

            if boxes is None or len(boxes) == 0:
                page_entry["faces_detected"] = 0
                result_summary["pages"].append(page_entry)
                continue

            faces_list = []
            for fi, bbox in enumerate(boxes):
                try:
                    x1, y1, x2, y2 = map(int, bbox.tolist())
                    # clamp to image bounds
                    x1 = max(0, min(x1, img.width - 1))
                    y1 = max(0, min(y1, img.height - 1))
                    x2 = max(0, min(x2, img.width - 1))
                    y2 = max(0, min(y2, img.height - 1))
                    w = x2 - x1
                    h = y2 - y1
                    if w <= 0 or h <= 0:
                        continue

                    # skip tiny boxes
                    if w < min_face_size or h < min_face_size:
                        # optionally attempt to expand box a little before skipping
                        # expand by padding proportional to min_face_size
                        pad = int(max(2, min_face_size * 0.5))
                        x1p = max(0, x1 - pad)
                        y1p = max(0, y1 - pad)
                        x2p = min(img.width, x2 + pad)
                        y2p = min(img.height, y2 + pad)
                        w2 = x2p - x1p
                        h2 = y2p - y1p
                        if w2 < min_face_size or h2 < min_face_size:
                            logger.debug(f"Skipping tiny face crop (w={w}, h={h}) on {file_path} page {page_idx}")
                            continue
                        # use expanded crop
                        crop = img.crop((x1p, y1p, x2p, y2p))
                    else:
                        crop = img.crop((x1, y1, x2, y2))

                    # optionally upscale very small crops before analysis (preserves aspect)
                    crop_to_analyze = crop
                    if upscale_small_faces and (crop.width < upscale_small_faces * 10 or crop.height < upscale_small_faces * 10):
                        new_w = int(round(crop.width * upscale_small_faces))
                        new_h = int(round(crop.height * upscale_small_faces))
                        # avoid zero sizes
                        new_w = max(16, new_w)
                        new_h = max(16, new_h)
                        crop_to_analyze = crop.resize((new_w, new_h), Image.BICUBIC)

                    # Save crop to disk
                    crop_name = f"page_{page_idx}_face_{fi+1}.jpg"
                    crop_path = output_subdir / crop_name
                    crop.save(crop_path, quality=80)

                    # Analyze with DeepFace
                    analysis = analyze_face(crop_to_analyze, upscale_small=upscale_small_faces)

                    faces_list.append({
                        "coords": [x1, y1, x2, y2],
                        "crop": str(crop_path),
                        "analysis": analysis if analysis else "no_face_detected"
                    })

                except Exception as e:
                    logger.exception(f"Failed processing face index {fi} on {file_path} page {page_idx}: {e}")
                    faces_list.append({
                        "coords": None,
                        "crop": None,
                        "analysis": f"face_processing_error: {e}"
                    })

            page_entry["faces_detected"] = len(faces_list)
            page_entry["faces"] = faces_list
            result_summary["pages"].append(page_entry)

    finally:
        try:
            pdf.close()
        except Exception:
            pass

    duration = time.time() - start_time
    result_summary["processing_time_s"] = round(duration, 2)

    # write JSON summary for this PDF
    try:
        out_json = output_subdir / f"{file_path.stem}.json"
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(result_summary, fh, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Failed to write JSON summary for {file_path}: {e}")

    return result_summary


def worker_init(mtcnn_thresholds: Optional[List[float]] = None, warm_deepface: bool = True):
    """
    Called once per process in the pool to initialize heavy objects (MTCNN, DeepFace warmup).
    """
    global _WORKER_MTCNN
    # initialize MTCNN once
    try:
        thresholds = mtcnn_thresholds if mtcnn_thresholds else [0.7, 0.8, 0.9]
        _WORKER_MTCNN = MTCNN(keep_all=True, device="cpu", thresholds=thresholds, post_process=True)
        logger.info("Worker: MTCNN initialized")
    except Exception as e:
        logger.exception(f"Worker: failed to init MTCNN: {e}")
        _WORKER_MTCNN = None

    if warm_deepface:
        try:
            # warm DeepFace once (enforce_detection=False so it doesn't require faces)
            DeepFace.analyze(np.zeros((100, 100, 3), dtype=np.uint8), actions=['age'], enforce_detection=False, silent=True)
            logger.info("Worker: DeepFace warmed")
        except Exception as e:
            logger.warning(f"Worker: DeepFace warm failed: {e}")


def worker_task(args_tuple):
    """Wrapper to satisfy Pool.map/imap_unordered single-arg requirement"""
    file_path, output_dir, dpi, min_face_size, upscale_small_faces = args_tuple
    return process_pdf(file_path, output_dir, dpi=dpi, min_face_size=min_face_size, upscale_small_faces=upscale_small_faces)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", help="Folder containing PDFs")
    parser.add_argument("--output_dir", default="./processed_output")
    parser.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() // 2)))
    parser.add_argument("--dpi", type=int, default=100, help="DPI when rendering PDF pages")
    parser.add_argument("--min-face-size", type=int, default=10, help="Minimum face crop width/height to keep")
    parser.add_argument("--upscale-small-faces", type=float, default=2.0, help="If small face crops, upscale by this factor before analysis (set <=1 to disable)")
    parser.add_argument("--mtcnn-thresholds", nargs=3, type=float, default=[0.7, 0.8, 0.9], help="MTCNN thresholds (p1 p2 p3)")
    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([str(f) for f in input_path.glob("**/*.pdf")])
    if not files:
        logger.info(f"No PDFs found in {input_path}")
        return

    logger.info(f"Found {len(files)} PDFs to process (workers={args.workers})")
    logger.info("Starting workers...")

    # Build tasks
    task_args = [(f, str(output_dir), args.dpi, args.min_face_size, args.upscale_small_faces) for f in files]

    start = time.time()
    results = []

    # If workers = 1, run in-process (simpler debugging)
    if args.workers <= 1:
        worker_init(mtcnn_thresholds=args.mtcnn_thresholds, warm_deepface=True)
        for ta in tqdm(task_args, desc="Processing PDFs"):
            results.append(worker_task(ta))
    else:
        # spawn pool with initializer to create one MTCNN per worker
        with mp.Pool(processes=args.workers, initializer=worker_init, initargs=(args.mtcnn_thresholds, True)) as pool:
            for res in tqdm(pool.imap_unordered(worker_task, task_args), total=len(task_args), desc="Processing PDFs"):
                results.append(res)

    end = time.time()
    logger.info(f"Completed in {end - start:.2f}s")
    logger.info(f"Output directory: {output_dir}")

    # Optionally write a master results JSON
    try:
        master_out = output_dir / "master_results.json"
        with open(master_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        logger.info(f"Wrote master results to {master_out}")
    except Exception as e:
        logger.exception(f"Failed to write master results JSON: {e}")

    # Print small summary to console
    for r in results:
        file = r.get("file") if isinstance(r, dict) else str(r)
        pages = len(r.get("pages", [])) if isinstance(r, dict) else 0
        faces_total = sum(p.get("faces_detected", 0) for p in r.get("pages", [])) if isinstance(r, dict) else 0
        logger.info(f"{file} -> pages={pages}, faces_total={faces_total}, error={r.get('error')}")

    return results


if __name__ == "__main__":
    main()
