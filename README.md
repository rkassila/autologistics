# Logistics Automation App

A simple logistics document processing application with PDF upload, text extraction, and structured field parsing using OpenAI.

## Features

- ✅ Streamlit UI for PDF document upload
- ✅ PDF text extraction (supports both text-based and scanned PDFs with OCR)
- ✅ OpenAI API integration for structured field extraction
- ✅ **Structured database columns** for extracted fields (not just JSONB)
- ✅ **GCP Cloud Storage** integration for storing original PDF documents
- ✅ FastAPI backend deployed on Cloud Run
- ✅ PostgreSQL Cloud SQL for data storage with proper connection checking
- ✅ Deduplication logic to prevent duplicate records
- ✅ Fully containerized with Docker

## Project Structure

```
autologistics/
├── app/                    # FastAPI backend
│   ├── main.py            # FastAPI application entry point
│   ├── router.py          # API routes
│   ├── processor.py       # PDF processing and OpenAI integration
│   ├── db.py              # Database connection and operations
│   ├── storage.py         # GCP Cloud Storage integration
│   └── schemas.py         # Pydantic models
├── streamlit_app/         # Streamlit frontend
│   └── app.py             # Streamlit UI
├── infra/                 # Infrastructure
│   └── schema.sql         # PostgreSQL schema
├── Dockerfile             # Docker configuration
├── requirements.txt       # Python dependencies
└── README.md

```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Database Configuration (PostgreSQL on GCP Cloud SQL)
DB_HOST=your-db-host
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=logistics_db
INSTANCE_CONNECTION_NAME=project:region:instance  # For Cloud SQL Unix socket connection

# GCP Cloud Storage
GCS_BUCKET_NAME=your-bucket-name
GCS_MAKE_PUBLIC=false  # Set to 'true' to make uploaded files publicly accessible
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json  # For local development

# OpenAI API
OPENAI_API_KEY=your-openai-api-key

# API Configuration
API_BASE_URL=http://localhost:8080/api/v1
PORT=8080
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL database (already exists on GCP Cloud SQL):
   - The app will **check connection** but **not recreate tables**
   - Ensure the schema has been run: `psql -U postgres -d logistics_db -f infra/schema.sql`
   - Or run it manually using Cloud SQL Admin or psql client

3. Configure GCP Cloud Storage:
   - Create a GCS bucket for storing PDFs
   - Set `GCS_BUCKET_NAME` environment variable
   - For local development, set up service account credentials

4. Run FastAPI backend:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

5. Run Streamlit frontend (in another terminal):
```bash
streamlit run streamlit_app/app.py
```

## Database Schema

The database uses **structured columns** for extracted fields:
- `tracking_number`, `shipper_name`, `receiver_name`
- `carrier`, `shipping_method`, `status`
- `shipment_date`, `delivery_date`
- `weight`, `dimensions`
- `storage_url` - Link to PDF in GCP Cloud Storage
- `additional_data` - JSONB for flexible additional fields

## Docker Deployment

Build and run with Docker:
```bash
docker build -t logistics-app .
docker run -p 8080:8080 --env-file .env logistics-app
```

For Cloud Run deployment, use the provided Dockerfile and deploy to Google Cloud Run.
