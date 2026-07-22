"""Simplified Face Verification Worker using MTCNN and best_face_verification_model.pkl."""

import os
import logging
from typing import Any, Dict, Optional
import numpy as np
import cv2

logger = logging.getLogger("kyc.face.worker")

_META_CLASSIFIER_CACHE = None

def load_meta_classifier():
    global _META_CLASSIFIER_CACHE
    if _META_CLASSIFIER_CACHE is None:
        try:
            import joblib
            model_path = os.path.join(os.path.dirname(__file__), "best_face_verification_model.pkl")
            if os.path.exists(model_path):
                _META_CLASSIFIER_CACHE = joblib.load(model_path)
                logger.info("Meta-classifier loaded successfully.")
            else:
                logger.error(f"Model file not found at {model_path}")
        except Exception as e:
            logger.error(f"Failed to load meta classifier: {e}")
    return _META_CLASSIFIER_CACHE

# Load immediately on boot
load_meta_classifier()

def compute_cosine_distance(emb_a: list, emb_b: list) -> float:
    """Calculate Cosine Distance: D = 1 - (A . B) / (||A||*||B||)."""
    if not emb_a or not emb_b or len(emb_a) != len(emb_b):
        return 1.0

    dot_product = sum(a * b for a, b in zip(emb_a, emb_b))
    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)

    if norm_a < 1e-6 or norm_b < 1e-6:
        return 1.0

    cos_sim = dot_product / (norm_a * norm_b)
    return float(max(0.0, min(2.0, 1.0 - cos_sim)))

def decode_image(image_bytes: bytes) -> Optional[np.ndarray]:
    if not image_bytes:
        return None
    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        logger.error(f"Failed to decode image bytes: {e}")
        return None

def perform_face_verification(primary_bytes: bytes, secondary_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    from deepface import DeepFace
    
    img1 = decode_image(primary_bytes)
    img2 = decode_image(secondary_bytes) if secondary_bytes else None
    
    default_resp = {
        "status": "NO_FACE",
        "ensemble_verdict": "NO_FACE_DETECTED",
        "match_confidence": 0.0,
        "mismatch_confidence": 100.0,
        "similarity": 0.0,
        "faces_detected": 0,
        "primary_bbox": None,
        "secondary_bbox": None,
        "model_disagreement": False,
        "quality_score": 0.0,
        "ensemble_distance": 1.0,
        "arcface_distance": 1.0,
        "facenet_distance": 1.0,
        "buffalo_distance": 1.0,
        "arcface_verdict": "MISMATCH",
        "facenet_verdict": "MISMATCH",
        "buffalo_verdict": "MISMATCH",
    }
    
    if img1 is None or img2 is None:
        return default_resp

    meta = load_meta_classifier()
    if not meta:
        default_resp["status"] = "ERROR"
        default_resp["ensemble_verdict"] = "ERROR"
        default_resp["message"] = "Model not loaded"
        return default_resp
        
    clf = meta["model"]
    scaler = meta.get("scaler")
    thresholds = meta.get("thresholds_per_model", {})
    models_used = meta.get("models_used", ["VGG-Face", "Facenet512", "ArcFace"])
    
    features = []
    distances = {}
    
    # Extract features matching the model training
    faces_detected = 0
    p_bbox = None
    s_bbox = None
    
    try:
        for m_name in models_used:
            try:
                # Use DeepFace with MTCNN as requested
                p_res = DeepFace.represent(img_path=img1, model_name=m_name, detector_backend="mtcnn", enforce_detection=True)
                s_res = DeepFace.represent(img_path=img2, model_name=m_name, detector_backend="mtcnn", enforce_detection=True)
                
                if p_res and s_res:
                    faces_detected = 2
                    if p_bbox is None:
                        p_bbox = p_res[0].get("facial_area")
                    if s_bbox is None:
                        s_bbox = s_res[0].get("facial_area")
                    
                p_emb = p_res[0]["embedding"]
                s_emb = s_res[0]["embedding"]
                
                dist = compute_cosine_distance(p_emb, s_emb)
            except Exception as e:
                logger.warning(f"Failed to get DeepFace embeddings for {m_name}: {e}")
                dist = 1.0
                
            distances[m_name] = dist
            thresh = thresholds.get(m_name, 0.5)
            norm_score = max(0.0, 1.0 - (dist / (thresh + 1e-10)))
            features.extend([float(dist), float(norm_score)])
            
        if faces_detected == 0:
            return default_resp
            
        X = np.array([features], dtype=np.float32)
        if scaler and not hasattr(clf, "named_steps"): 
            X = scaler.transform(X)
            
        if hasattr(clf, "predict_proba"):
            probs = clf.predict_proba(X)[0]
            match_prob = float(probs[1])
            mismatch_prob = float(probs[0])
            pred_class = int(np.argmax(probs))
        else:
            pred_class = int(clf.predict(X)[0])
            match_prob = 1.0 if pred_class == 1 else 0.0
            mismatch_prob = 1.0 - match_prob
            
        final_verdict = "MATCH" if pred_class == 1 else "MISMATCH"
        
        # Build response with backward compatibility for gateway
        resp = dict(default_resp)
        resp.update({
            "status": "COMPLETED",
            "ensemble_verdict": final_verdict,
            "similarity": round(match_prob * 100.0, 2),
            "match_confidence": round(match_prob * 100.0, 1),
            "mismatch_confidence": round(mismatch_prob * 100.0, 1),
            "faces_detected": faces_detected,
            "primary_bbox": p_bbox,
            "secondary_bbox": s_bbox,
            "quality_score": 100.0,
            "ensemble_distance": float(np.mean(list(distances.values()))) if distances else 1.0,
        })
        
        # Inject specific distances if available
        for k, v in distances.items():
            k_lower = k.lower().replace("-", "")
            resp[f"{k_lower}_distance"] = v
            resp[f"{k_lower}_verdict"] = "MATCH" if v < thresholds.get(k, 0.5) else "MISMATCH"
            
        return resp
        
    except Exception as e:
        logger.error(f"Face verification failed: {e}")
        default_resp.update({"status": "ERROR", "ensemble_verdict": "ERROR", "message": str(e)})
        return default_resp


def process_face_verification_job(job_id_str: str, current_user_id_str: str):
    import json
    import uuid
    from datetime import datetime, timezone
    from redis import Redis
    from ai_platform.db.session import SessionLocal
    from ai_platform.db.models import (
        VerificationJob, Document, FaceResult, VerificationResult, 
        VerificationScore, AuditLog, JobStatus, VerificationDecision, DocumentRole
    )
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = Redis.from_url(redis_url, socket_keepalive=True, retry_on_timeout=True)
    
    def notify_job_subscribers(job_id: str, event_data: dict):
        try:
            channel = f"job_events:{job_id}"
            redis_conn.publish(channel, json.dumps(event_data))
        except Exception as e:
            logger.error(f"Failed to publish to redis pubsub: {e}")

    logger.info(f"Worker picked up job {job_id_str} for user {current_user_id_str}")
    
    db = SessionLocal()
    try:
        job_uuid = uuid.UUID(job_id_str)
        current_user_id = uuid.UUID(current_user_id_str)
        job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid, VerificationJob.user_id == current_user_id).first()
        if not job:
            return

        job.status = JobStatus.FACE_VERIFICATION
        db.commit()
        notify_job_subscribers(job_id_str, {"event_type": "face.started", "status": "face_verification"})

        docs = db.query(Document).filter(Document.job_id == job.id, Document.user_id == current_user_id).all()
        primary_bytes = None
        secondary_bytes = None

        for doc in docs:
            doc_bytes = doc.file_content
            if doc.role == DocumentRole.PRIMARY:
                primary_bytes = doc_bytes
            else:
                secondary_bytes = doc_bytes

        face_report = perform_face_verification(primary_bytes or b"", secondary_bytes)

        verdict_str = face_report["ensemble_verdict"]
        similarity_score = face_report["similarity"]
        faces_count = face_report["faces_detected"]
        p_bbox = face_report["primary_bbox"]

        if verdict_str == "MATCH":
            decision = VerificationDecision.VERIFIED
        elif verdict_str == "REVIEW_REQUIRED":
            decision = VerificationDecision.REVIEW_REQUIRED
        else:
            decision = VerificationDecision.REJECTED

        primary_doc = [d for d in docs if d.role == DocumentRole.PRIMARY]
        primary_doc_id = primary_doc[0].id if primary_doc else docs[0].id

        face_res = FaceResult(
            user_id=current_user_id, 
            job_id=job.id,
            primary_document_id=primary_doc_id,
            status="completed" if faces_count > 0 else "no_face",
            faces_detected_count=faces_count,
            match_verdict=verdict_str,
            similarity_score=similarity_score / 100.0,
            confidence_score=face_report["match_confidence"] / 100.0 if verdict_str == "MATCH" else face_report["mismatch_confidence"] / 100.0,
            face_bbox=p_bbox,
        )
        db.add(face_res)

        field_matches = {
            "face_verification": face_report,
            "final_verification": {
                "score": similarity_score,
                "verdict": verdict_str,
            },
        }

        report_json = {
            "verdict": verdict_str,
            "verification_score": similarity_score,
            "match_confidence": face_report["match_confidence"],
            "mismatch_confidence": face_report["mismatch_confidence"],
            "model_disagreement": face_report["model_disagreement"],
            "quality_score": face_report["quality_score"],
            "face_verification": face_report,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

        verif_res = VerificationResult(
            user_id=current_user_id, 
            job_id=job.id,
            decision=decision,
            overall_score=similarity_score / 100.0,
            face_match_score=similarity_score / 100.0,
            field_matches=field_matches,
            report_json=report_json,
        )
        db.add(verif_res)

        score_rec = VerificationScore(
            user_id=current_user_id, 
            job_id=job.id,
            verdict=verdict_str,
            final_score=similarity_score,
            breakdown=field_matches,
        )
        db.add(score_rec)

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)

        audit_comp = AuditLog(
            user_id=current_user_id, 
            action="FORENSIC_FACE_VERIFICATION_COMPLETED",
            resource_type="verification_job",
            resource_id=job_id_str,
            payload={
                "arcface_distance": face_report.get("arcface_distance", 1.0),
                "facenet_distance": face_report.get("facenet_distance", 1.0),
                "buffalo_distance": face_report.get("buffalo_distance", 1.0),
                "ensemble_distance": face_report.get("ensemble_distance", 1.0),
                "arcface_verdict": face_report.get("arcface_verdict", "MISMATCH"),
                "facenet_verdict": face_report.get("facenet_verdict", "MISMATCH"),
                "buffalo_verdict": face_report.get("buffalo_verdict", "MISMATCH"),
                "ensemble_verdict": face_report.get("ensemble_verdict", "MISMATCH"),
                "match_confidence": face_report.get("match_confidence", 0.0),
                "mismatch_confidence": face_report.get("mismatch_confidence", 100.0),
                "model_disagreement": face_report.get("model_disagreement", False),
                "quality_score": face_report.get("quality_score", 0.0),
                "self_similarity_passed": face_report.get("self_similarity_check", {}).get("passed", True),
            },
        )
        db.add(audit_comp)
        db.commit()

        notify_job_subscribers(
            job_id_str,
            {
                "event_type": "report.generated",
                "status": "completed",
                "decision": decision.value,
                "overall_score": similarity_score,
            },
        )
    except Exception as e:
        logger.error("Async face verification pipeline failed for job %s: %s", job_id_str, str(e))
        try:
            job = db.query(VerificationJob).filter(VerificationJob.id == uuid.UUID(job_id_str)).first()
            if job:
                job.status = JobStatus.FAILED
                job.status_reason = str(e)
                db.commit()
        except:
            pass
        notify_job_subscribers(job_id_str, {"event_type": "verification.failed", "status": "failed", "error": str(e)})
    finally:
        db.close()
        logger.info(f"Worker finished job {job_id_str}")


if __name__ == "__main__":
    import os
    import sys
    from redis import Redis
    from rq import Worker, Queue, Connection
    
    logger.setLevel(logging.INFO)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = Redis.from_url(redis_url)
    
    logger.info("Starting Face Verification Redis Worker Daemon...")
    with Connection(redis_conn):
        worker = Worker(["face_tasks"])
        worker.work()
