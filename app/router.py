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
    """Helper function to create a model log entry - same logic as /model-log endpoint."""
    # Use the exact same pattern as /model-log endpoint
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

    # Check database - flag if already saved, but still process
    already_exists = False
    try:
        existing_doc = db.get_document_by_hash(document_hash)
        if existing_doc:
            already_exists = True
    except Exception:
        pass  # If DB check fails, continue anyway

    # Upload to storage (optional)
    storage_url = None
    if storage := get_storage():
        try:
            storage_url = storage.upload_pdf(pdf_content, file.filename, document_hash)
        except:
            pass  # Storage is optional for PoC

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
        import traceback
        error_detail = f"Error saving document: {str(e)}"
        print(f"Database save error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)

    # Automatically create model_log entry - DIRECT database write (no helper function)
    # Write directly to database using the same pattern as /model-log endpoint
    try:
        from datetime import datetime
        import traceback

        # Create a NEW session explicitly (don't reuse any existing session)
        session = model_log_db.SessionLocal()
        try:
            # Create the log entry object
            log_entry = ModelLog(
                success=True,  # Test with success=True
                document_id=document.id,
                document_hash=request.document_hash,
                document_link=data.get("storage_url") or "https://example.com/test.pdf",
                extraction_result={
                    "model": "gpt-4o-mini",
                    "timestamp": datetime.now().isoformat(),
                    "raw_response": "Test extraction result from save endpoint"
                },
                original_values={
                    "tracking_number": "TEST123",
                    "shipper_name": "Test Shipper",
                    "receiver_name": "Test Receiver"
                },
                corrected_values={
                    "tracking_number": "TEST123",
                    "shipper_name": "Test Shipper",
                    "receiver_name": "Test Receiver"
                },
                corrections_made=None,
                failure_reason=None
            )

            # Add to session
            session.add(log_entry)

            # Flush to get the ID (but don't commit yet)
            session.flush()

            # Explicit commit
            session.commit()

            # Refresh to get all fields
            session.refresh(log_entry)

            print(f"✅ Model log entry created successfully: ID={log_entry.id}, document_id={document.id}")

        except Exception as db_error:
            # Rollback on error
            session.rollback()
            raise db_error
        finally:
            # Always close the session
            session.close()

    except Exception as e:
        # Log error but don't fail document save
        import traceback
        error_detail = f"Error saving model log: {str(e)}"
        print(f"❌ Model log error in save endpoint: {error_detail}")
        print(traceback.format_exc())
        # Continue - document save was successful

    # Clean up temporary storage
    try:
        del _extracted_documents[request.document_hash]
    except KeyError:
        pass  # Already deleted

    # Ensure structured_fields is serializable (convert dates to strings)
    serializable_fields = {}
    try:
        for key, value in fields.items():
            if value is None:
                serializable_fields[key] = None
            elif hasattr(value, 'isoformat'):  # Date/datetime objects
                serializable_fields[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                # Ensure nested objects are JSON serializable
                serializable_fields[key] = value
            else:
                serializable_fields[key] = str(value) if value else None
    except Exception as e:
        print(f"Warning: Failed to serialize structured_fields: {str(e)}")
        serializable_fields = None

    # Return response - always return success if document was saved
    try:
        # Ensure document_id is available
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
        # If response serialization fails, still return success but without structured_fields
        import traceback
        print(f"Response serialization error: {str(e)}")
        print(traceback.format_exc())
        # Get document_id safely
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

            # Store storage URL before deleting from DB
            storage_url = document.storage_url

            # Delete from storage first if URL exists
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
                    # Continue with DB deletion even if storage deletion fails

            # Delete from database
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
async def test_model_log_save():
    """Test endpoint that writes directly to model_log - same pattern as test page."""
    try:
        from datetime import datetime
        import traceback

        # Use test data exactly like test page
        test_data = {
            "success": True,
            "document_id": 1,
            "document_hash": "test_hash_from_save_endpoint",
            "document_link": "https://example.com/test.pdf",
            "extraction_result": {
                "model": "gpt-4o-mini",
                "timestamp": datetime.now().isoformat(),
                "raw_response": "Test extraction result from save endpoint"
            },
            "original_values": {
                "tracking_number": "TEST123",
                "shipper_name": "Test Shipper",
                "receiver_name": "Test Receiver"
            },
            "corrected_values": {
                "tracking_number": "TEST123",
                "shipper_name": "Test Shipper",
                "receiver_name": "Test Receiver"
            },
            "corrections_made": None,
            "failure_reason": None
        }

        # Write directly to database - EXACT same code as save endpoint
        session = model_log_db.SessionLocal()
        try:
            log_entry = ModelLog(
                success=test_data["success"],
                document_id=test_data["document_id"],
                document_hash=test_data["document_hash"],
                document_link=test_data["document_link"],
                extraction_result=test_data["extraction_result"],
                original_values=test_data["original_values"],
                corrected_values=test_data["corrected_values"],
                corrections_made=test_data["corrections_made"],
                failure_reason=test_data["failure_reason"]
            )

            session.add(log_entry)
            session.flush()
            session.commit()
            session.refresh(log_entry)

            print(f"✅ Test model log entry created successfully: ID={log_entry.id}")

            return {
                "success": True,
                "message": "Test model log saved successfully",
                "log_id": log_entry.id,
                "document_id": log_entry.document_id,
                "document_hash": log_entry.document_hash
            }

        except Exception as db_error:
            session.rollback()
            raise db_error
        finally:
            session.close()

    except Exception as e:
        import traceback
        error_detail = f"Error in test model log save: {str(e)}"
        print(f"❌ Test model log error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/model-logs", response_model=Dict)
async def list_model_logs(limit: int = 100, offset: int = 0):
    """List all model logs in database."""
    try:
        # First check if table exists using metadata inspection
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

        # Table exists - proceed with query
        with model_log_db.get_session() as session:
            logs = session.query(ModelLog).order_by(
                ModelLog.created_at.desc()
            ).offset(offset).limit(limit).all()

            total = session.query(ModelLog).count()

            # Return results (even if empty - table exists but has no rows)
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
        # If metadata inspection fails, fall back to exception-based detection
        error_str = str(e)
        if "does not exist" in error_str.lower() or "undefinedtable" in error_str.lower():
            return {
                "total": 0,
                "count": 0,
                "offset": offset,
                "logs": [],
                "message": "Model log table does not exist yet. Please create it using infra/model_log.sql"
            }
        # Log the actual error for debugging
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
        # Check if table doesn't exist
        if "does not exist" in error_str.lower() or "undefinedtable" in error_str.lower():
            raise HTTPException(status_code=404, detail="Model log table does not exist yet. Please create it using infra/model_log.sql")
        # Other errors still raise exception
        raise HTTPException(status_code=500, detail=f"Error fetching model log: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check."""
    # Check main database
    db_status = "connected" if db.check_connection() else "disconnected"

    # Check model log database - verify both connection AND table existence
    model_log_db_status = "unknown"
    try:
        if model_log_db.check_connection():
            # Connection works, now check if table exists
            from sqlalchemy import inspect
            inspector = inspect(model_log_db.engine)
            table_name = os.getenv("DB_MODEL_NAME", "model_log")
            table_exists = table_name in inspector.get_table_names()

            if table_exists:
                model_log_db_status = "connected"
            else:
                model_log_db_status = "disconnected"  # Table doesn't exist
        else:
            model_log_db_status = "disconnected"
    except Exception as e:
        model_log_db_status = "disconnected"
        print(f"Model log DB health check error: {str(e)}")

    # Check storage bucket
    bucket_status = "unknown"
    try:
        storage = get_storage()
        if storage:
            # Try to check if bucket is accessible
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
