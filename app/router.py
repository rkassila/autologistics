"""FastAPI routes for document processing."""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import Dict
from app.schemas import (
    DocumentExtractResponse, DocumentSaveRequest, DocumentUploadResponse,
    ModelLogRequest, ModelLogResponse
)
from app.processor import process_document
from app.db import db, compute_document_hash
from app.model_db import ModelLog, model_log_db
from app.storage import get_storage

router = APIRouter()
_extracted_documents = {}


def create_model_log_entry(
    success: bool,
    document_id: int,
    document_hash: str,
    document_link: str = None,
    extraction_result: dict = None,
    original_values: dict = None,
    corrected_values: dict = None,
    corrections_made: dict = None,
    failure_reason: str = None
) -> ModelLog:
    """Creates a model log entry in the database."""
    with model_log_db.get_session() as session:
        log_entry = ModelLog(
            success=success,
            document_id=document_id,
            document_hash=document_hash,
            document_link=document_link,
            extraction_result=extraction_result,
            original_values=original_values,
            corrected_values=corrected_values,
            corrections_made=corrections_made,
            failure_reason=failure_reason
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry


@router.post("/extract", response_model=DocumentExtractResponse)
async def extract_document(file: UploadFile = File(...)) -> DocumentExtractResponse:
    """Extract document without saving."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    pdf_content = await file.read()
    document_hash = compute_document_hash(pdf_content)

    # Check if document was already processed
    already_exists = False
    try:
        existing_doc = db.get_document_by_hash(document_hash)
        if existing_doc:
            already_exists = True
    except Exception:
        pass

    # Upload to cloud storage if configured
    storage_url = None
    if storage := get_storage():
        try:
            storage_url = storage.upload_pdf(pdf_content, file.filename, document_hash)
        except:
            pass

    extracted_text, structured_fields, additional_data, is_valid, validation_message = process_document(
        pdf_content, file.filename
    )

    # Keep extracted data in memory for the save endpoint
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
        storage_url=storage_url,
        already_exists=already_exists
    )


@router.post("/save", response_model=DocumentUploadResponse)
async def save_document(request: DocumentSaveRequest = Body(...)) -> DocumentUploadResponse:
    """Save extracted document."""
    if request.document_hash not in _extracted_documents:
        raise HTTPException(status_code=404, detail="Document not found")

    data = _extracted_documents[request.document_hash]
    fields = request.structured_fields or data["structured_fields"]

    # Prevent duplicate saves from concurrent requests
    try:
        if db.get_document_by_hash(request.document_hash):
            del _extracted_documents[request.document_hash]
            raise HTTPException(status_code=400, detail="Document already exists")
    except HTTPException:
        raise
    except Exception:
        pass
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
        import traceback
        error_detail = f"Error saving document: {str(e)}"
        print(f"Database save error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)

    # Create model log entry for quality tracking
    try:
        import traceback

        # Get original and reviewed fields for comparison
        original_fields = data.get("structured_fields", {})
        reviewed_fields = fields

        def make_json_serializable(val):
            """Converts Python objects to JSON-compatible types."""
            if val is None:
                return None
            if hasattr(val, 'isoformat'):
                return val.isoformat()
            if isinstance(val, (dict, list)):
                if isinstance(val, dict):
                    return {k: make_json_serializable(v) for k, v in val.items()}
                else:
                    return [make_json_serializable(item) for item in val]
            return val

        # Compare only editable fields to detect changes
        corrections_made = {}
        for key in reviewed_fields.keys():
            original_val = original_fields.get(key)
            reviewed_val = reviewed_fields.get(key)

            def normalize_val(v):
                """Normalizes values for comparison - empty strings become None."""
                if v is None:
                    return None
                if isinstance(v, str):
                    stripped = v.strip()
                    return stripped if stripped else None
                if hasattr(v, 'isoformat'):
                    return v.isoformat()
                return str(v) if v else None

            orig_norm = normalize_val(original_val)
            rev_norm = normalize_val(reviewed_val)

            # Record actual changes, ignoring None/empty comparisons
            if orig_norm != rev_norm:
                if orig_norm is not None or rev_norm is not None:
                    corrections_made[key] = {
                        "original": make_json_serializable(original_val),
                        "corrected": make_json_serializable(reviewed_val)
                    }

        success = len(corrections_made) == 0

        original_values_serialized = {k: make_json_serializable(v) for k, v in original_fields.items()}
        reviewed_values_serialized = {k: make_json_serializable(v) for k, v in reviewed_fields.items()}

        session = model_log_db.SessionLocal()
        try:
            log_entry = ModelLog(
                success=success,
                document_id=document.id,
                document_hash=request.document_hash,
                document_link=data.get("storage_url"),
                extraction_result=data.get("additional_data"),
                original_values=original_values_serialized,
                corrected_values=reviewed_values_serialized,
                corrections_made=corrections_made if corrections_made else None,
                failure_reason=None if success else f"Corrections made to {len(corrections_made)} field(s): {', '.join(corrections_made.keys())}"
            )

            session.add(log_entry)
            session.flush()
            session.commit()
            session.refresh(log_entry)

            print(f"✅ Model log entry created successfully: ID={log_entry.id}, document_id={document.id}")

        except Exception as db_error:
            session.rollback()
            raise db_error
        finally:
            session.close()

    except Exception as e:
        # Model log failure shouldn't block document save
        import traceback
        error_detail = f"Error saving model log: {str(e)}"
        print(f"❌ Model log error in save endpoint: {error_detail}")
        print(traceback.format_exc())

    # Remove from temporary cache
    try:
        del _extracted_documents[request.document_hash]
    except KeyError:
        pass

    # Convert date objects to strings for JSON response
    serializable_fields = {}
    try:
        for key, value in fields.items():
            if value is None:
                serializable_fields[key] = None
            elif hasattr(value, 'isoformat'):
                serializable_fields[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                serializable_fields[key] = value
            else:
                serializable_fields[key] = str(value) if value else None
    except Exception as e:
        print(f"Warning: Failed to serialize structured_fields: {str(e)}")
        serializable_fields = None

    try:
        document_id = document.id if hasattr(document, 'id') and document.id else None
        response = DocumentUploadResponse(
            message="Saved",
            document_id=document_id,
            is_duplicate=False,
            structured_fields=serializable_fields,
            storage_url=data["storage_url"]
        )
        return response
    except Exception as e:
        # Fallback response if serialization fails
        import traceback
        print(f"Response serialization error: {str(e)}")
        print(traceback.format_exc())
        document_id = None
        try:
            document_id = document.id if hasattr(document, 'id') else None
        except:
            pass
        return DocumentUploadResponse(
            message="Saved",
            document_id=document_id,
            is_duplicate=False,
            structured_fields=None,
            storage_url=data.get("storage_url")
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


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int) -> Dict[str, str]:
    """Delete a document by ID, including the stored file if it exists."""
    try:
        with db.get_session() as session:
            from app.db import LogisticsDocument
            document = session.query(LogisticsDocument).filter(LogisticsDocument.id == document_id).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            storage_url = document.storage_url

            # Try to delete file from cloud storage first
            storage_deleted = False
            if storage_url:
                try:
                    storage = get_storage()
                    if storage:
                        storage_deleted = storage.delete_file(storage_url)
                        if storage_deleted:
                            print(f"Deleted file from storage: {storage_url}")
                        else:
                            print(f"Warning: File not found in storage or deletion failed: {storage_url}")
                except Exception as e:
                    print(f"Warning: Error deleting file from storage: {str(e)}")
            session.delete(document)
            session.commit()

            message = f"Document {document_id} deleted successfully"
            if storage_url:
                if storage_deleted:
                    message += " (file deleted from storage)"
                else:
                    message += " (storage file deletion attempted)"

            return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error deleting document: {str(e)}"
        print(f"Delete error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/model-log", response_model=ModelLogResponse)
async def log_model_quality(request: ModelLogRequest = Body(...)) -> ModelLogResponse:
    """Log model quality data (success/failure with corrections)."""
    try:
        log_entry = create_model_log_entry(
            success=request.success,
            document_id=request.document_id,
            document_hash=request.document_hash,
            document_link=request.document_link,
            extraction_result=request.extraction_result,
            original_values=request.original_values,
            corrected_values=request.corrected_values,
            corrections_made=request.corrections_made,
            failure_reason=request.failure_reason
        )

        return ModelLogResponse(
            message="Model log saved",
            log_id=log_entry.id
        )
    except Exception as e:
        import traceback
        error_detail = f"Error saving model log: {str(e)}"
        print(f"Model log error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/test-model-log-save")
async def test_model_log_save(request: Dict = Body(...)):
    """Save to model_log using real document data."""
    try:
        from datetime import datetime
        import traceback

        document_hash = request.get("document_hash")
        document_id = request.get("document_id")
        original_fields = request.get("original_fields", {})
        reviewed_fields = request.get("reviewed_fields", {})
        additional_data = request.get("additional_data", {})
        storage_url = request.get("storage_url")

        if not document_hash:
            raise HTTPException(status_code=400, detail="document_hash is required")

        # Look up document ID if not provided
        if document_id is None:
            try:
                existing_doc = db.get_document_by_hash(document_hash)
                if existing_doc:
                    document_id = existing_doc.id
            except Exception:
                pass

        def make_json_serializable(val):
            """Converts Python objects to JSON-compatible types."""
            if val is None:
                return None
            if hasattr(val, 'isoformat'):
                return val.isoformat()
            if isinstance(val, (dict, list)):
                if isinstance(val, dict):
                    return {k: make_json_serializable(v) for k, v in val.items()}
                else:
                    return [make_json_serializable(item) for item in val]
            return val

        # Compare only editable fields to avoid false positives
        corrections_made = {}
        for key in reviewed_fields.keys():
            original_val = original_fields.get(key)
            reviewed_val = reviewed_fields.get(key)

            def normalize_val(v):
                """Normalizes values for comparison - empty strings become None."""
                if v is None:
                    return None
                if isinstance(v, str):
                    stripped = v.strip()
                    return stripped if stripped else None
                if hasattr(v, 'isoformat'):
                    return v.isoformat()
                return str(v) if v else None

            orig_norm = normalize_val(original_val)
            rev_norm = normalize_val(reviewed_val)

            # Record actual changes, ignoring None/empty comparisons
            if orig_norm != rev_norm:
                if orig_norm is not None or rev_norm is not None:
                    corrections_made[key] = {
                        "original": make_json_serializable(original_val),
                        "corrected": make_json_serializable(reviewed_val)
                    }

        success = len(corrections_made) == 0

        original_values_serialized = {k: make_json_serializable(v) for k, v in original_fields.items()}
        reviewed_values_serialized = {k: make_json_serializable(v) for k, v in reviewed_fields.items()}
        session = model_log_db.SessionLocal()
        try:
            log_entry = ModelLog(
                success=success,
                document_id=document_id,
                document_hash=document_hash,
                document_link=storage_url,
                extraction_result=additional_data,
                original_values=original_values_serialized,
                corrected_values=reviewed_values_serialized,
                corrections_made=corrections_made if corrections_made else None,
                failure_reason=None if success else f"Corrections made to {len(corrections_made)} field(s): {', '.join(corrections_made.keys())}"
            )

            session.add(log_entry)
            session.flush()
            session.commit()
            session.refresh(log_entry)

            print(f"✅ Model log entry created successfully: ID={log_entry.id}, document_id={document_id}, document_hash={document_hash}")

            return {
                "success": True,
                "message": "Model log saved successfully",
                "log_id": log_entry.id,
                "document_id": log_entry.document_id,
                "document_hash": log_entry.document_hash
            }

        except Exception as db_error:
            session.rollback()
            raise db_error
        finally:
            session.close()

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error in model log save: {str(e)}"
        print(f"❌ Model log error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/model-logs", response_model=Dict)
async def list_model_logs(limit: int = 100, offset: int = 0):
    """List all model logs in database."""
    try:
        # Verify table exists before querying
        from sqlalchemy import inspect
        inspector = inspect(model_log_db.engine)
        table_name = os.getenv("DB_MODEL_NAME", "model_log")
        table_exists = table_name in inspector.get_table_names()

        if not table_exists:
            return {
                "total": 0,
                "count": 0,
                "offset": offset,
                "logs": [],
                "message": "Model log table does not exist yet. Please create it using infra/model_log.sql"
            }

        with model_log_db.get_session() as session:
            logs = session.query(ModelLog).order_by(
                ModelLog.created_at.desc()
            ).offset(offset).limit(limit).all()

            total = session.query(ModelLog).count()

            return {
                "total": total,
                "count": len(logs),
                "offset": offset,
                "logs": [
                    {
                        "id": log.id,
                        "success": log.success,
                        "document_id": log.document_id,
                        "document_hash": log.document_hash,
                        "document_link": log.document_link,
                        "corrections_made": log.corrections_made,
                        "failure_reason": log.failure_reason,
                        "created_at": str(log.created_at)
                    }
                    for log in logs
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        # Handle table missing errors gracefully
        error_str = str(e)
        if "does not exist" in error_str.lower() or "undefinedtable" in error_str.lower():
            return {
                "total": 0,
                "count": 0,
                "offset": offset,
                "logs": [],
                "message": "Model log table does not exist yet. Please create it using infra/model_log.sql"
            }
        import traceback
        print(f"Unexpected error in list_model_logs: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error fetching model logs: {str(e)}")


@router.get("/model-logs/{log_id}", response_model=Dict)
async def get_model_log(log_id: int) -> Dict:
    """Retrieve a model log by ID."""
    try:
        with model_log_db.get_session() as session:
            log = session.query(ModelLog).filter(ModelLog.id == log_id).first()
            if not log:
                raise HTTPException(status_code=404, detail="Model log not found")

            return {
                "id": log.id,
                "success": log.success,
                "document_id": log.document_id,
                "document_hash": log.document_hash,
                "document_link": log.document_link,
                "extraction_result": log.extraction_result,
                "original_values": log.original_values,
                "corrected_values": log.corrected_values,
                "corrections_made": log.corrections_made,
                "failure_reason": log.failure_reason,
                "created_at": str(log.created_at)
            }
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "does not exist" in error_str.lower() or "undefinedtable" in error_str.lower():
            raise HTTPException(status_code=404, detail="Model log table does not exist yet. Please create it using infra/model_log.sql")
        raise HTTPException(status_code=500, detail=f"Error fetching model log: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check."""
    db_status = "connected" if db.check_connection() else "disconnected"

    # Verify model log table exists, not just connection
    model_log_db_status = "unknown"
    try:
        if model_log_db.check_connection():
            from sqlalchemy import inspect
            inspector = inspect(model_log_db.engine)
            table_name = os.getenv("DB_MODEL_NAME", "model_log")
            table_exists = table_name in inspector.get_table_names()

            if table_exists:
                model_log_db_status = "connected"
            else:
                model_log_db_status = "disconnected"
        else:
            model_log_db_status = "disconnected"
    except Exception as e:
        model_log_db_status = "disconnected"
        print(f"Model log DB health check error: {str(e)}")

    bucket_status = "unknown"
    try:
        storage = get_storage()
        if storage:
            bucket_status = "connected"
        else:
            bucket_status = "not_configured"
    except:
        bucket_status = "disconnected"

    return {
        "status": "ok",
        "database": db_status,
        "model_log_db": model_log_db_status,
        "bucket": bucket_status
    }
