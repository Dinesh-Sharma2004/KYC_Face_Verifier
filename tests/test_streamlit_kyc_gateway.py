from ai_platform.frontend.kyc_gateway import (
    build_verification_summary,
    document_hash,
    mask_identifier,
    parse_nodes,
    stable_customer_id,
)


def test_parse_nodes_supports_csv_config():
    nodes = parse_nodes("Node A,http://localhost:8000,unified,secret\nNode B,http://localhost:8001,legacy_kyc,key")

    assert len(nodes) == 2
    assert nodes[0].name == "Node A"
    assert nodes[1].kind == "legacy_kyc"


def test_stable_customer_id_and_document_hash_are_deterministic():
    assert stable_customer_id("Rahul Mehta", "CRM-1") == stable_customer_id("Rahul Mehta", "CRM-1")
    assert document_hash(b"document") == document_hash(b"document")


def test_mask_identifier_keeps_only_last_digits():
    assert mask_identifier("1234 5678 9012") == "********9012"
    assert mask_identifier("ABCDE1234F") == "******234F"


def test_build_verification_summary_from_legacy_kyc_payload():
    client_payload = {
        "documents": {
            "client_document": {
                "extracted_data": {"full_name_en": "Rahul Mehta"},
            }
        }
    }
    kyc_payload = [
        {
            "full_name": "Rahul Mehta",
            "documents": {
                "aadhaar_card": {
                    "front_data": {
                        "full_name_en": "Rahul Mehta",
                        "aadhaar_number": "123456789012",
                    }
                },
                "pan_card": {
                    "full_name_en": "Rahul Mehta",
                    "pan_number": "ABCDE1234F",
                },
            },
        }
    ]

    summary = build_verification_summary(client_payload, kyc_payload, expected_name="Rahul Mehta")

    assert summary["status"] == "verified"
    assert summary["checks"]["aadhaar_found"] is True
    assert summary["checks"]["pan_found"] is True
    assert summary["identity"]["aadhaar_number"] == "********9012"
