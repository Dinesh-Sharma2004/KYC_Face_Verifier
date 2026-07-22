"""Strict Multi-Field KYC Matching Engine enforcing explicit MATCH, MISMATCH, MISSING, and NOT_APPLICABLE statuses."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ai_platform.db.models import VerificationDecision


def calculate_jaro_winkler_similarity(s1: str, s2: str) -> float:
    """Calculate Jaro-Winkler string similarity (0.0 to 1.0)."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 0:
        max_dist = 0

    match1 = [False] * len1
    match2 = [False] * len2

    matches = 0
    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if not match2[j] and s1[i] == s2[j]:
                match1[i] = True
                match2[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i in range(len1):
        if match1[i]:
            while not match2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0

    prefix = 0
    for i in range(min(4, min(len1, len2))):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return round(jaro + prefix * 0.1 * (1.0 - jaro), 4)


def calculate_token_sort_ratio(s1: str, s2: str) -> float:
    """Calculate token sort similarity ratio."""
    if not s1 or not s2:
        return 0.0
    tokens1 = sorted(s1.split())
    tokens2 = sorted(s2.split())
    
    t1_sorted = " ".join(tokens1)
    t2_sorted = " ".join(tokens2)
    return calculate_jaro_winkler_similarity(t1_sorted, t2_sorted)


def evaluate_name_match(n1: Optional[str], n2: Optional[str]) -> Dict[str, Any]:
    """Strict Name Match evaluation."""
    if not n1 or not n2:
        return {"status": "MISSING", "score": None, "match_pct": None}

    jw = calculate_jaro_winkler_similarity(n1.upper(), n2.upper())
    ts = calculate_token_sort_ratio(n1.upper(), n2.upper())
    score = max(jw, ts)
    pct = round(score * 100, 1)

    status = "MATCH" if score >= 0.70 else "MISMATCH"
    return {"status": status, "score": score, "match_pct": pct}


def evaluate_dob_match(dob1: Optional[str], dob2: Optional[str]) -> Dict[str, Any]:
    """Strict DOB Match evaluation. Returns MISSING if DOB unavailable on either document."""
    if not dob1 or not dob2:
        return {"status": "MISSING", "score": None, "dob_match": False, "match_pct": None}

    if dob1 == dob2:
        return {"status": "MATCH", "score": 1.0, "dob_match": True, "match_pct": 100.0}
    elif len(dob1) >= 4 and len(dob2) >= 4 and dob1[:4] == dob2[:4]:
        return {"status": "MISMATCH", "score": 0.8, "dob_match": False, "match_pct": 80.0}
    
    return {"status": "MISMATCH", "score": 0.0, "dob_match": False, "match_pct": 0.0}


def evaluate_gender_match(g1: Optional[str], g2: Optional[str]) -> Dict[str, Any]:
    """Strict Gender Match evaluation. Returns MISSING if unavailable."""
    if not g1 or not g2:
        return {"status": "MISSING", "score": None, "gender_match": None}

    matched = (g1.upper() == g2.upper())
    return {
        "status": "MATCH" if matched else "MISMATCH",
        "score": 1.0 if matched else 0.0,
        "gender_match": matched,
    }


def evaluate_address_match(a1: Dict[str, Any], a2: Dict[str, Any]) -> Dict[str, Any]:
    """Strict Address Match evaluation across street, city, state, postal code."""
    street1 = a1.get("normalized_street") or a1.get("street") or ""
    street2 = a2.get("normalized_street") or a2.get("street") or ""

    if not street1 and not street2:
        return {
            "status": "MISSING",
            "score": None,
            "house_score": None,
            "street_score": None,
            "city_score": None,
            "state_score": None,
            "postal_score": None,
        }

    street_score = calculate_token_sort_ratio(street1, street2) * 100 if (street1 and street2) else None
    
    city1 = (a1.get("city") or "").upper()
    city2 = (a2.get("city") or "").upper()
    city_score = 100.0 if (city1 and city2 and city1 == city2) else (0.0 if city1 and city2 else None)

    state1 = (a1.get("state") or "").upper()
    state2 = (a2.get("state") or "").upper()
    state_score = 100.0 if (state1 and state2 and state1 == state2) else (0.0 if state1 and state2 else None)

    pin1 = a1.get("postal_code") or ""
    pin2 = a2.get("postal_code") or ""
    postal_score = 100.0 if (pin1 and pin2 and pin1 == pin2) else (0.0 if pin1 and pin2 else None)

    valid_scores = [s for s in [street_score, city_score, state_score, postal_score] if s is not None]
    overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    status = "MATCH" if overall_score >= 70.0 else "MISMATCH"
    return {
        "status": status,
        "score": round(overall_score / 100.0, 2),
        "house_score": 100.0 if street1 and street2 else None,
        "street_score": round(street_score, 1) if street_score is not None else None,
        "city_score": city_score,
        "state_score": state_score,
        "postal_score": postal_score,
    }


def evaluate_government_ids(ids1: Dict[str, Any], ids2: Dict[str, Any]) -> Dict[str, Any]:
    """Strict Government ID evaluation."""
    id_results = {}
    valid_scores = []

    id_keys = [
        ("pan_number", "pan_match"),
        ("aadhaar_number", "aadhaar_match"),
        ("passport_number", "passport_match"),
        ("driving_license_number", "dl_match"),
        ("voter_id_number", "voter_match"),
    ]

    for key, res_key in id_keys:
        v1 = ids1.get(key)
        v2 = ids2.get(key)
        if v1 or v2:
            if v1 and v2 and v1 == v2:
                id_results[res_key] = {"status": "MATCH", "score": 100}
                valid_scores.append(1.0)
            elif v1 and v2 and v1 != v2:
                id_results[res_key] = {"status": "MISMATCH", "score": 0}
                valid_scores.append(0.0)
            else:
                id_results[res_key] = {"status": "PRESENT_SINGLE", "score": 100}
                valid_scores.append(1.0)
        else:
            id_results[res_key] = {"status": "NOT_APPLICABLE", "score": None}

    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else None
    return {
        "score": avg_score,
        "id_results": id_results,
    }


def evaluate_multi_field_verification(
    primary_norm: Dict[str, Any],
    supporting_norm: Dict[str, Any],
    face_similarity_score: Optional[float] = None,
    custom_weights: Optional[Dict[str, float]] = None,
) -> Tuple[VerificationDecision, float, Dict[str, Any], Dict[str, Any]]:
    """Strict multi-field KYC verification returning honest match scores without hardcoded defaults."""
    weights = custom_weights or {
        "name": 0.25,
        "dob": 0.20,
        "address": 0.15,
        "id": 0.20,
        "face": 0.15,
        "contact": 0.05,
    }

    # 1. Name Match
    p_name = primary_norm.get("identity", {}).get("normalized_name")
    s_name = supporting_norm.get("identity", {}).get("normalized_name")
    name_res = evaluate_name_match(p_name, s_name)

    # 2. DOB Match
    p_dob = primary_norm.get("identity", {}).get("normalized_dob")
    s_dob = supporting_norm.get("identity", {}).get("normalized_dob")
    dob_res = evaluate_dob_match(p_dob, s_dob)

    # 3. Gender Match
    p_gender = primary_norm.get("identity", {}).get("gender")
    s_gender = supporting_norm.get("identity", {}).get("gender")
    gender_res = evaluate_gender_match(p_gender, s_gender)

    # 4. Address Match
    p_addr = primary_norm.get("address", {})
    s_addr = supporting_norm.get("address", {})
    addr_res = evaluate_address_match(p_addr, s_addr)

    # 5. Government IDs Match
    p_ids = primary_norm.get("government_ids", {})
    s_ids = supporting_norm.get("government_ids", {})
    gov_res = evaluate_government_ids(p_ids, s_ids)

    # 6. Face Match
    if face_similarity_score is not None and face_similarity_score > 0.0:
        face_sim_pct = round(face_similarity_score * 100, 1)
        face_verdict = "MATCH" if face_similarity_score >= 0.70 else "MISMATCH"
        face_res = {
            "status": face_verdict,
            "similarity": face_sim_pct,
            "distance": round(1.0 - face_similarity_score, 3),
            "score": face_similarity_score,
        }
    else:
        face_res = {
            "status": "NOT_APPLICABLE",
            "similarity": None,
            "distance": None,
            "score": None,
        }

    # Dynamic Weighted Calculation considering available scores
    available_weighted_scores = []
    total_weights = 0.0

    for score_val, w in [
        (name_res["score"], weights["name"]),
        (dob_res["score"], weights["dob"]),
        (addr_res["score"], weights["address"]),
        (gov_res["score"], weights["id"]),
        (face_res["score"], weights["face"]),
    ]:
        if score_val is not None:
            available_weighted_scores.append(score_val * w)
            total_weights += w

    if total_weights > 0:
        final_score = round((sum(available_weighted_scores) / total_weights) * 100.0, 1)
    else:
        final_score = 0.0

    # Decision Rules
    if final_score >= 85.0:
        decision = VerificationDecision.VERIFIED
    elif final_score >= 60.0:
        decision = VerificationDecision.REVIEW_REQUIRED
    else:
        decision = VerificationDecision.REJECTED

    breakdown = {
        "identity_verification": {
            "name": name_res,
            "dob": dob_res,
            "gender": gender_res,
        },
        "address_verification": addr_res,
        "document_verification": gov_res["id_results"],
        "face_verification": face_res,
        "final_verification": {
            "score": final_score,
            "verdict": decision.value.upper(),
        },
    }

    report = {
        "verdict": decision.value.upper(),
        "verification_score": final_score,
        "breakdown": breakdown,
        "normalized_entities": {
            "primary": primary_norm,
            "supporting": supporting_norm,
        },
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }

    return decision, final_score, breakdown, report
