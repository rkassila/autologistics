"""GCP Cloud Storage integration for PDF storage."""

import os
from typing import Optional
from google.cloud import storage
from datetime import datetime


class CloudStorage:
    """GCP Cloud Storage manager for storing PDF documents."""

    def __init__(self):
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "")
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME environment variable is required")

        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_pdf(self, pdf_content: bytes, filename: str, document_hash: str) -> str:
        """Upload PDF to Cloud Storage and return the URL."""
        now = datetime.now()
        blob_name = f"documents/{now.year}/{now.month:02d}/{document_hash}/{filename}"
        blob = self.bucket.blob(blob_name)
        blob.content_type = "application/pdf"
        blob.upload_from_string(pdf_content, content_type="application/pdf")

        if os.getenv("GCS_MAKE_PUBLIC", "false").lower() == "true":
            blob.make_public()
            return blob.public_url
        return f"gs://{self.bucket_name}/{blob_name}"


def get_storage() -> Optional[CloudStorage]:
    """Get Cloud Storage instance if configured."""
    try:
        if os.getenv("GCS_BUCKET_NAME"):
            return CloudStorage()
    except Exception as e:
        print(f"Warning: Cloud Storage not available: {str(e)}")
    return None
