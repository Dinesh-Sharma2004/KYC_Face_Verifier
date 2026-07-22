from __future__ import annotations

import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_platform.frontend.kyc_gateway import (
    BackendNode,
    KycGateway,
    append_job,
    build_verification_summary,
    document_hash,
    load_ledger,
    new_job_id,
    parse_nodes,
    record_customer,
    save_ledger,
    stable_customer_id,
    utc_now_iso,
)


LEDGER_PATH = ROOT_DIR / "ai_platform" / "frontend" / "data" / "customer_kyc_ledger.json"
UPLOAD_ROOT = ROOT_DIR / "ai_platform" / "frontend" / "uploads"


def css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f7f8fb; color: #17202a; }
        section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #dde3ea; }
        h1, h2, h3 { letter-spacing: 0; }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #dde3ea;
            border-radius: 8px;
            padding: 12px;
        }
        .status-ok { color: #0f766e; font-weight: 700; }
        .status-review { color: #b45309; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def file_payload(uploaded_files: list[Any], customer_id: str, job_id: str, role: str) -> tuple[list[tuple[str, bytes, str]], list[dict[str, Any]]]:
    files: list[tuple[str, bytes, str]] = []
    metadata: list[dict[str, Any]] = []
    target_dir = UPLOAD_ROOT / customer_id / job_id / role
    target_dir.mkdir(parents=True, exist_ok=True)

    for uploaded in uploaded_files:
        content = uploaded.getvalue()
        filename = uploaded.name
        path = target_dir / filename
        path.write_bytes(content)
        mime_type = uploaded.type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        files.append((filename, content, mime_type))
        metadata.append(
            {
                "uploaded_filename": filename,
                "user_id": customer_id,
                "doc_type": "KYC" if role == "kyc" else "CLIENT_DOCUMENT",
                "role": role,
                "sha256": document_hash(content),
                "local_path": str(path),
            }
        )
    return files, metadata


def node_choice(nodes: list[BackendNode], label: str, key: str) -> BackendNode:
    names = [f"{node.name} ({node.kind})" for node in nodes]
    selected = st.selectbox(label, names, key=key)
    return nodes[names.index(selected)]


def submit_to_node(node: BackendNode, files: list[tuple[str, bytes, str]], metadata: list[dict[str, Any]]) -> tuple[str, Any]:
    if not files:
        return "skipped", {"message": "No files uploaded for this document group."}
    try:
        return "succeeded", KycGateway(node).submit(files, metadata)
    except Exception as exc:  # requests surfaces useful HTTP context here
        return "failed", {"error": str(exc), "node": node.name}


def render_summary(summary: dict[str, Any]) -> None:
    status = summary["status"]
    if status == "verified":
        st.markdown('<p class="status-ok">Verified</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-review">Review required</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    checks = summary["checks"]
    c1.metric("Client docs", checks["client_documents_processed"])
    c2.metric("KYC docs", checks["kyc_documents_processed"])
    c3.metric("Aadhaar", "Found" if checks["aadhaar_found"] else "Missing")
    c4.metric("PAN", "Found" if checks["pan_found"] else "Missing")
    st.json(summary)


def main() -> None:
    st.set_page_config(page_title="Startrit KYC Console", layout="wide")
    css()

    st.title("Startrit Client Document and KYC Verification")
    st.caption("Centralized customer console with decentralized backend node routing.")

    ledger = load_ledger(LEDGER_PATH)
    node_config = os.getenv("STARTRIT_BACKEND_NODES", "")
    with st.sidebar:
        st.subheader("Backend Nodes")
        raw_nodes = st.text_area(
            "Node config",
            value=node_config,
            height=120,
            placeholder="Node A,http://127.0.0.1:8000,unified,secret123",
        )
        try:
            nodes = parse_nodes(raw_nodes)
        except Exception as exc:
            st.error(str(exc))
            nodes = parse_nodes("")
        st.write(f"{len(nodes)} node(s) configured")

    customers = ledger.get("customers", {})
    jobs = ledger.get("jobs", [])

    tab_intake, tab_jobs, tab_customers, tab_nodes = st.tabs(["Intake", "Verification Jobs", "Customers", "Node Sync"])

    with tab_intake:
        left, right = st.columns([0.9, 1.1])
        with left:
            st.subheader("Customer")
            customer_name = st.text_input("Client name", placeholder="Rahul Mehta")
            external_id = st.text_input("Customer reference", placeholder="CRM-1024")
            customer_id = stable_customer_id(customer_name, external_id) if customer_name else ""
            st.text_input("Customer ID", value=customer_id, disabled=True)
            tenant_id = st.text_input("Tenant or branch", placeholder="north-zone")

            st.subheader("Routing")
            client_node = node_choice(nodes, "Client document node", "client_node")
            kyc_node = node_choice(nodes, "KYC document node", "kyc_node")

        with right:
            st.subheader("Documents")
            client_docs = st.file_uploader(
                "Client documents",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                help="Upload the document you want to verify against the client identity.",
            )
            kyc_docs = st.file_uploader(
                "KYC documents",
                type=["png", "jpg", "jpeg", "pdf"],
                accept_multiple_files=True,
                help="Upload Aadhaar or PAN separately from the client document.",
            )

        if st.button("Verify Customer", type="primary", use_container_width=True):
            if not customer_name or not customer_id:
                st.warning("Enter a client name before verification.")
            elif not client_docs and not kyc_docs:
                st.warning("Upload at least one client document or KYC document.")
            else:
                job_id = new_job_id()
                customer = {
                    "customer_id": customer_id,
                    "name": customer_name,
                    "external_id": external_id,
                    "tenant_id": tenant_id,
                }
                record_customer(ledger, customer)

                client_files, client_meta = file_payload(client_docs or [], customer_id, job_id, "client")
                kyc_files, kyc_meta = file_payload(kyc_docs or [], customer_id, job_id, "kyc")

                with st.spinner("Submitting to backend nodes and syncing the central ledger..."):
                    client_status, client_result = submit_to_node(client_node, client_files, client_meta)
                    kyc_status, kyc_result = submit_to_node(kyc_node, kyc_files, kyc_meta)
                    summary = build_verification_summary(client_result, kyc_result, expected_name=customer_name)

                job = {
                    "job_id": job_id,
                    "customer_id": customer_id,
                    "tenant_id": tenant_id,
                    "created_at": utc_now_iso(),
                    "client_node": client_node.name,
                    "kyc_node": kyc_node.name,
                    "client_status": client_status,
                    "kyc_status": kyc_status,
                    "summary": summary,
                    "client_metadata": client_meta,
                    "kyc_metadata": kyc_meta,
                    "client_result": client_result,
                    "kyc_result": kyc_result,
                }
                append_job(ledger, job)
                save_ledger(LEDGER_PATH, ledger)
                render_summary(summary)

    with tab_jobs:
        st.subheader("Verification Jobs")
        if not jobs:
            st.info("No jobs recorded yet.")
        for job in jobs[:50]:
            customer = customers.get(job.get("customer_id"), {})
            with st.expander(f"{job.get('created_at', '')} | {customer.get('name', job.get('customer_id'))} | {job.get('summary', {}).get('status', 'unknown')}"):
                render_summary(job.get("summary", {}))
                st.json(
                    {
                        "job_id": job.get("job_id"),
                        "client_node": job.get("client_node"),
                        "kyc_node": job.get("kyc_node"),
                        "client_status": job.get("client_status"),
                        "kyc_status": job.get("kyc_status"),
                    }
                )

    with tab_customers:
        st.subheader("Customers")
        c1, c2, c3 = st.columns(3)
        c1.metric("Customers", len(customers))
        c2.metric("Jobs", len(jobs))
        c3.metric("Verified", sum(1 for job in jobs if job.get("summary", {}).get("status") == "verified"))
        st.dataframe(
            [
                {
                    "customer_id": customer_id,
                    "name": data.get("name"),
                    "external_id": data.get("external_id"),
                    "tenant_id": data.get("tenant_id"),
                    "updated_at": data.get("updated_at"),
                }
                for customer_id, data in customers.items()
            ],
            use_container_width=True,
        )

    with tab_nodes:
        st.subheader("Node Sync")
        st.caption("Health checks keep the central console aware of decentralized processing nodes.")
        if st.button("Check Nodes", use_container_width=True):
            for node in nodes:
                try:
                    health = KycGateway(node).health()
                    st.success(f"{node.name}: online")
                    st.json(health)
                except Exception as exc:
                    st.error(f"{node.name}: {exc}")


if __name__ == "__main__":
    main()
