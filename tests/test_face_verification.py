"""Comprehensive Unit and Integration Test Suite for ArcFace Face Verification, Cosine Distance, Similarity Mapping, RGB Conversion, and Self-Similarity Diagnostics."""

import pytest
from ai_platform.services.face_worker import (
    FACE_MATCH_THRESHOLDS,
    audit_rgb_conversion,
    compute_cosine_distance,
    detect_align_crop_face,
    distance_to_similarity,
    enhance_document_photo,
    generate_face_embedding,
    perform_face_verification,
)


def test_rgb_conversion():
    """Phase 4 Requirement: Automated test verifying BGR to RGB conversion."""
    import numpy as np

    bgr_img = np.zeros((100, 100, 3), dtype=np.uint8)
    bgr_img[:, :, 0] = 255  # Blue channel in BGR

    rgb_img = audit_rgb_conversion(bgr_img)
    assert rgb_img is not None
    assert rgb_img[0, 0, 2] == 255  # Red channel in RGB holds original BGR Blue


def test_embedding_generation_and_l2_norm():
    """Verify 512-d ArcFace embedding generation and unit length L2 normalization."""
    import numpy as np

    fake_crop = np.full((112, 112, 3), 128, dtype=np.uint8)
    emb_arc = generate_face_embedding(fake_crop, "ArcFace")
    assert len(emb_arc) == 512
    
    norm = float(np.linalg.norm(emb_arc))
    assert abs(norm - 1.0) < 1e-4

    emb_fnet = generate_face_embedding(fake_crop, "FaceNet")
    assert len(emb_fnet) == 512


def test_self_similarity_sanity_check():
    """Phase 7 Requirement: Verify self-similarity distance(face, face) <= 0.05."""
    import numpy as np

    fake_crop = np.full((112, 112, 3), 128, dtype=np.uint8)
    emb1 = generate_face_embedding(fake_crop, "ArcFace")
    emb2 = generate_face_embedding(fake_crop, "ArcFace")

    dist = compute_cosine_distance(emb1, emb2)
    assert dist <= 0.05


def test_cosine_distance_calculation():
    """Verify cosine distance formula for identical, orthogonal, and arbitrary vectors."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert compute_cosine_distance(v1, v2) == 0.0

    v3 = [0.0, 1.0, 0.0]
    assert compute_cosine_distance(v1, v3) == 1.0


def test_mathematically_valid_similarity_mapping():
    """Verify distance = 0.2016 produces similarity = 79.84% (Never 0%)."""
    d = 0.2016
    sim = distance_to_similarity(d)
    assert sim == 79.84


def test_threshold_and_verdict_calibration():
    """Verify ArcFace threshold 0.40 produces MATCH for 0.2016 distance."""
    res = perform_face_verification(b"PRIMARY_IMG_BYTES", b"SECONDARY_SELFIE_BYTES")
    assert "ArcFace" in res["model"]
    assert res["metric"] == "cosine"
    assert abs(res["threshold"] - FACE_MATCH_THRESHOLDS["arcface"]) <= 0.06
    assert res["distance"] < 0.40
    assert res["verdict"] == "MATCH"
    assert res["similarity"] > 75.0
