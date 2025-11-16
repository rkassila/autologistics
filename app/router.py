"""FastAPI routes for document processing."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import Dict
from app.schemas import DocumentExtractResponse, DocumentSaveRequest, DocumentUploadResponse
from app.processor import process_document
from app.db import db, compute_document_hash
from app.storage import get_storage

router = APIRouter()
_extracted_documents = {}


@router.post("/extract", response_model=DocumentExtractResponse)
async def extract_document(file: UploadFile = File(...)) -> DocumentExtractResponse:
    """Extract document without saving."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    pdf_content = await file.read()
    document_hash = compute_document_hash(pdf_content)

    # Check database - only block if already saved
    existing_doc = db.get_document_by_hash(document_hash)
    if existing_doc:
        raise HTTPException(
            status_code=400,
            detail=f"Document already exists in database (ID: {existing_doc.id})"
        )

    # Upload to storage (optional)
    storage_url = None
    if storage := get_storage():
        try:
            storage_url = storage.upload_pdf(pdf_content, file.filename, document_hash)
        except:
            pass  # Storage optional for PoC

    # Process
    extracted_text, structured_fields, additional_data, is_valid, validation_message = process_document(
        pdf_content, file.filename
    )

    # Store temporarily
    _extracted_documents[document_hash] = {
        "filename": file.filename,
        "storage_url": storage_url,
        "extracted_text": extracted_text,
        "structured_fields": structured_fields,
        "additional_data": additional_data
    }

    return DocumentExtractResponse(
        message="Extracted" if is_valid else "Invalid document",
        is_valid=is_valid,
        validation_message=validation_message,
        document_hash=document_hash,
        extracted_text=extracted_text if is_valid else None,
        structured_fields=structured_fields if is_valid else None,
        storage_url=storage_url
    )


@router.post("/save", response_model=DocumentUploadResponse)
async def save_document(request: DocumentSaveRequest = Body(...)) -> DocumentUploadResponse:
    """Save extracted document."""
    if request.document_hash not in _extracted_documents:
        raise HTTPException(status_code=404, detail="Document not found")

    data = _extracted_documents[request.document_hash]
    fields = request.structured_fields or data["structured_fields"]

    if db.get_document_by_hash(request.document_hash):
        del _extracted_documents[request.document_hash]
        raise HTTPException(status_code=400, detail="Document already exists")

    document = db.save_document(
        filename=request.filename or data["filename"],
        storage_url=data["storage_url"],
        extracted_text=data["extracted_text"],
        document_hash=request.document_hash,
        structured_fields=fields,
        additional_data=data.get("additional_data")
    )

    del _extracted_documents[request.document_hash]

    return DocumentUploadResponse(
        message="Saved",
        document_id=document.id,
        is_duplicate=False,
        structured_fields=fields
    )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check."""
    return {"status": "ok", "database": "connected" if db.check_connection() else "disconnected"}
