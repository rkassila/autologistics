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

    def delete_file(self, storage_url: str) -> bool:
        """Delete a file from Cloud Storage given its URL."""
        try:
            # Handle different URL formats: gs://bucket/path or https://storage.googleapis.com/...
            if storage_url.startswith("gs://"):
                # Extract blob path from gs://bucket/path
                path = storage_url.replace(f"gs://{self.bucket_name}/", "")
            elif "storage.googleapis.com" in storage_url or "storage.cloud.google.com" in storage_url:
                # Extract blob path from public URL
                # Format: https://storage.googleapis.com/bucket/path or https://storage.cloud.google.com/bucket/path
                parts = storage_url.split(f"/{self.bucket_name}/")
                if len(parts) > 1:
                    path = parts[1].split("?")[0]  # Remove query parameters
                else:
                    return False
            else:
                # Try to extract path directly if it's a relative path
                path = storage_url

            blob = self.bucket.blob(path)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file from storage: {str(e)}")
            return False


def get_storage() -> Optional[CloudStorage]:
    """Get Cloud Storage instance if configured."""
    try:
        if os.getenv("GCS_BUCKET_NAME"):
            return CloudStorage()
    except Exception as e:
        print(f"Warning: Cloud Storage not available: {str(e)}")
    return None
