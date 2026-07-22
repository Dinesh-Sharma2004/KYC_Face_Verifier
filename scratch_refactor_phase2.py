import re

def main():
    with open("ai_platform/services/gateway.py", "r", encoding="utf-8") as f:
        code = f.read()

    # 1. Fix run_async_verification_pipeline
    old_fetch_logic = """        storage = get_storage_client()
        bucket = "kyc-documents"

        job.status = JobStatus.FACE_VERIFICATION
        db.commit()
        notify_job_subscribers(job_id_str, {"event_type": "face.started", "status": "face_verification"})

        docs = db.query(Document).filter(Document.job_id == job.id, Document.user_id == current_user_id).all()
        primary_bytes = None
        secondary_bytes = None

        for doc in docs:
            version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).first()
            key = version.storage_key if version else f"{job_id_str}/{doc.role.value}/{doc.original_filename}"

            try:
                doc_bytes = storage.get_object(bucket, key)
            except Exception as ex:
                logger.error("Failed to read document from storage key %s: %s", key, str(ex))
                doc_bytes = b""

            if doc.role == DocumentRole.PRIMARY:
                primary_bytes = doc_bytes
            else:
                secondary_bytes = doc_bytes"""

    new_fetch_logic = """        job.status = JobStatus.FACE_VERIFICATION
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
                secondary_bytes = doc_bytes"""

    code = code.replace(old_fetch_logic, new_fetch_logic)

    # 2. Fix get_job_face_debug_gallery
    old_gallery = """    docs = db.query(Document).filter(Document.job_id == job.id, Document.user_id == current_user_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")

    storage = get_storage_client()
    bucket = "kyc-documents"

    # Serve the primary document image
    primary = [d for d in docs if d.role == DocumentRole.PRIMARY]
    doc = primary[0] if primary else docs[0]

    version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).first()
    key = version.storage_key if version else f"{job_id}/{doc.role.value}/{doc.original_filename}"

    try:
        content = storage.get_object(bucket, key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve document from storage")"""

    new_gallery = """    docs = db.query(Document).filter(Document.job_id == job.id, Document.user_id == current_user_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")

    primary = [d for d in docs if d.role == DocumentRole.PRIMARY]
    doc = primary[0] if primary else docs[0]
    
    content = doc.file_content
    if not content:
        raise HTTPException(status_code=500, detail="Failed to retrieve document content from DB")"""

    code = code.replace(old_gallery, new_gallery)
    
    # 3. Fix get_job_face_debug
    old_debug = """    docs = db.query(Document).filter(Document.job_id == job.id, Document.user_id == current_user_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")

    storage = get_storage_client()
    bucket = "kyc-documents"

    primary = [d for d in docs if d.role == DocumentRole.PRIMARY]
    doc = primary[0] if primary else docs[0]

    version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).first()
    key = version.storage_key if version else f"{job_id}/{doc.role.value}/{doc.original_filename}"

    try:
        content = storage.get_object(bucket, key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve document from storage")"""
        
    code = code.replace(old_debug, new_gallery) # Uses the same replacement logic

    # Remove storage client import
    code = code.replace("from ai_platform.storage.client import get_storage_client\n", "")
    
    # Also remove get_storage_client from upload_document which we missed earlier
    code = code.replace("    storage = get_storage_client()\n", "")
    code = code.replace("    bucket = \"kyc-documents\"\n", "")
    
    # Remove DocumentVersion import if it's there
    code = code.replace("DocumentVersion,\n", "")

    with open("ai_platform/services/gateway.py", "w", encoding="utf-8") as f:
        f.write(code)
    
    print("Gateway refactored to use DB instead of R2.")

if __name__ == "__main__":
    main()
