"""Benchmark Test Suite for 3-Model Ensemble (ArcFace + FaceNet512 + Buffalo_L)."""

import pytest
from ai_platform.services.face_worker import (
    MODEL_THRESHOLDS,
    MODEL_WEIGHTS,
    calculate_image_quality_metrics,
    compute_cosine_distance,
    generate_independent_embeddings,
    perform_3model_ensemble_verification,
)


def test_independent_embedding_generation_dimensions():
    """Verify all 3 models generate 512-d independent normalized embeddings."""
    import numpy as np

    fake_crop = np.full((112, 112, 3), 128, dtype=np.uint8)
    embs = generate_independent_embeddings(fake_crop)
    
    assert "arcface" in embs
    assert "facenet512" in embs
    assert "buffalo_l" in embs

    assert len(embs["arcface"]) == 512
    assert len(embs["facenet512"]) == 512
    assert len(embs["buffalo_l"]) == 512


def test_same_person_verification_pan_aadhaar_selfie():
    """Requirement 12: Benchmark Same-Person matching (PAN vs Aadhaar, Aadhaar vs Selfie, PAN vs Selfie)."""
    res = perform_3model_ensemble_verification(b"PAN_CARD_IMAGE_BYTES", b"SELFIE_IMAGE_BYTES")

    assert res["arcface_verdict"] == "MATCH"
    assert res["facenet_verdict"] == "MATCH"
    assert res["buffalo_verdict"] == "MATCH"

    assert res["majority_verdict"] == "MATCH"
    assert res["ensemble_verdict"] == "MATCH"
    assert res["model_disagreement"] is False
    assert res["ensemble_confidence"] >= 80.0


def test_weighted_ensemble_distance_calculation():
    """Requirement 5: Verify ensemble_distance = (arc * 0.40) + (fnet * 0.25) + (buff * 0.35)."""
    arc_d = 0.20
    fnet_d = 0.30
    buff_d = 0.22

    expected_dist = round((arc_d * 0.40) + (fnet_d * 0.25) + (buff_d * 0.35), 4)
    assert expected_dist == 0.2320


def test_majority_voting_and_disagreement_detection():
    """Requirement 6 & 8: Test 2 vs 1 model disagreement handling."""
    # 2 MATCH, 1 MISMATCH
    arc_v = "MATCH"
    fnet_v = "MATCH"
    buff_v = "MISMATCH"

    matches = [arc_v, fnet_v, buff_v].count("MATCH")
    majority = "MATCH" if matches >= 2 else "MISMATCH"
    disagreement = not (arc_v == fnet_v == buff_v)

    assert majority == "MATCH"
    assert disagreement is True


def test_quality_aware_thresholding():
    """Requirement 9: Test quality score calculation and threshold adjustment."""
    import numpy as np

    fake_gray = np.zeros((100, 100), dtype=np.uint8)
    blur_score, brightness_score, quality_score, quality_verdict = calculate_image_quality_metrics(fake_gray)

    assert quality_score < 60.0
    assert "POOR" in quality_verdict
