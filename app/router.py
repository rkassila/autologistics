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
    try:
        existing_doc = db.get_document_by_hash(document_hash)
        if existing_doc:
            raise HTTPException(
                status_code=400,
                detail=f"Document already exists in database (ID: {existing_doc.id})"
            )
    except HTTPException:
        raise
    except Exception:
        pass  # If DB check fails, continue anyway

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

    # Check if already saved (race condition protection)
    try:
        if db.get_document_by_hash(request.document_hash):
            del _extracted_documents[request.document_hash]
            raise HTTPException(status_code=400, detail="Document already exists")
    except HTTPException:
        raise
    except Exception:
        pass  # If check fails, continue anyway

    # Save to database
    try:
        document = db.save_document(
            filename=request.filename or data["filename"],
            storage_url=data["storage_url"],
            extracted_text=data["extracted_text"],
            document_hash=request.document_hash,
            structured_fields=fields,
            additional_data=data.get("additional_data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving document: {str(e)}")

    # Clean up temporary storage
    try:
        del _extracted_documents[request.document_hash]
    except KeyError:
        pass  # Already deleted

    # Ensure structured_fields is serializable (convert dates to strings)
    serializable_fields = {}
    for key, value in fields.items():
        if hasattr(value, 'isoformat'):  # Date/datetime objects
            serializable_fields[key] = value.isoformat()
        else:
            serializable_fields[key] = value

    return DocumentUploadResponse(
        message="Saved",
        document_id=document.id,
        is_duplicate=False,
        structured_fields=serializable_fields
    )


@router.get("/documents", response_model=Dict)
async def list_documents(limit: int = 100, offset: int = 0):
    """List all documents in database."""
    with db.get_session() as session:
        from app.db import LogisticsDocument
        documents = session.query(LogisticsDocument).order_by(
            LogisticsDocument.created_at.desc()
        ).offset(offset).limit(limit).all()

        total = session.query(LogisticsDocument).count()

        return {
            "total": total,
            "count": len(documents),
            "offset": offset,
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "tracking_number": doc.tracking_number,
                    "shipper_name": doc.shipper_name,
                    "receiver_name": doc.receiver_name,
                    "carrier": doc.carrier,
                    "shipment_date": str(doc.shipment_date) if doc.shipment_date else None,
                    "status": doc.status,
                    "created_at": str(doc.created_at),
                    "storage_url": doc.storage_url
                }
                for doc in documents
            ]
        }


@router.get("/documents/{document_id}", response_model=Dict)
async def get_document(document_id: int) -> Dict:
    """Retrieve a parsed document by ID."""
    with db.get_session() as session:
        from app.db import LogisticsDocument
        document = session.query(LogisticsDocument).filter(LogisticsDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "id": document.id,
            "filename": document.filename,
            "tracking_number": document.tracking_number,
            "shipper_name": document.shipper_name,
            "shipper_address": document.shipper_address,
            "receiver_name": document.receiver_name,
            "receiver_address": document.receiver_address,
            "carrier": document.carrier,
            "shipping_method": document.shipping_method,
            "weight": document.weight,
            "dimensions": document.dimensions,
            "status": document.status,
            "shipment_date": str(document.shipment_date) if document.shipment_date else None,
            "delivery_date": str(document.delivery_date) if document.delivery_date else None,
            "special_instructions": document.special_instructions,
            "storage_url": document.storage_url,
            "created_at": str(document.created_at),
            "additional_data": document.additional_data
        }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check."""
    return {"status": "ok", "database": "connected" if db.check_connection() else "disconnected"}
