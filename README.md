# Logistics Automation Backend

FastAPI backend for logistics document processing with PDF extraction, structured field parsing using OpenAI, PostgreSQL & bucket cloud storage and model quality tracking.

**Frontend Repository:** [autologistics-front](https://github.com/rkassila/autologistics-front)

## Features

- PDF text extraction (supports both text-based and scanned PDFs with OCR)
- OpenAI API integration for structured field extraction and document validation
- PostgreSQL database with structured columns for extracted fields
- GCP Cloud Storage integration for storing original PDF documents
- Model quality logging to track extraction success and manual corrections
- Deduplication logic to prevent duplicate records
- Two-step workflow: Extract & Review → Save
- RESTful API endpoints for document and model log management

## Project Structure

```
autologistics/
├── app/                    # FastAPI backend
│   ├── main.py            # FastAPI application entry point
│   ├── router.py          # API routes
│   ├── processor.py       # PDF processing and OpenAI integration
│   ├── db.py              # Logistics documents database operations
│   ├── model_db.py        # Model log database operations
│   ├── storage.py         # GCP Cloud Storage integration
│   └── schemas.py         # Pydantic models
├── infra/                 # Infrastructure
│   └── logistics_db.sql   # PostgreSQL schema (both tables)
├── Dockerfile             # Docker configuration
├── requirements.txt       # Python dependencies
└── README.md
```

## Database Schema

The application uses a single PostgreSQL database (`logistics_db`) with two tables:

### `logistics_documents` Table
Stores processed logistics documents with structured fields:
- `tracking_number`, `shipper_name`, `shipper_address`
- `receiver_name`, `receiver_address`
- `carrier`, `shipping_method`, `status`
- `shipment_date`, `delivery_date` (DATE type)
- `weight`, `dimensions`
- `storage_url` - Link to PDF in GCP Cloud Storage
- `additional_data` - JSONB for flexible additional fields
- `created_at`, `updated_at` - Timestamps

### `model_log` Table
Tracks model extraction quality and manual corrections:
- `success` - Boolean indicating if extraction was correct
- `document_id` - Reference to logistics_documents
- `document_hash` - Document hash for tracking
- `extraction_result` - JSONB with model metadata
- `original_values` - JSONB with original extracted values
- `corrected_values` - JSONB with user-corrected values
- `corrections_made` - JSONB mapping field names to corrections
- `failure_reason` - Text description of corrections needed
- `created_at` - Timestamp

## Local Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root directory:

```env
# Database Configuration
# For Cloud SQL (Unix socket connection):
INSTANCE_CONNECTION_NAME=project-id:region:instance-name

# For local PostgreSQL:
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=logistics_db
DB_TABLE_NAME=logistics_documents
DB_MODEL_NAME=model_log

# GCP Cloud Storage (Optional)
GCS_BUCKET_NAME=your-bucket-name
GCS_MAKE_PUBLIC=false
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# OpenAI API (Required)
OPENAI_API_KEY=sk-your-openai-api-key

# API Configuration
PORT=8080
```

### 3. Database Setup

Run the schema to create both tables:

```bash
psql -U postgres -d logistics_db -f infra/logistics_db.sql
```

Or use Cloud SQL Admin SQL Editor if using Cloud SQL.

### 4. Run Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

The API will be available at `http://localhost:8080`

## API Endpoints

### Document Endpoints
- `GET /api/v1/health` - Health check (database, model log, storage)
- `POST /api/v1/extract` - Extract document (returns preview, doesn't save)
- `POST /api/v1/save` - Save extracted document to database (automatically creates model log entry)
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document and storage file

### Model Log Endpoints
- `POST /api/v1/model-log` - Manually create model log entry
- `POST /api/v1/test-model-log-save` - Save model log with real document data
- `GET /api/v1/model-logs` - List all model logs
- `GET /api/v1/model-logs/{id}` - Get model log details

## Deployment to Google Cloud Run

### Prerequisites

- Google Cloud Project created
- Billing enabled
- `gcloud` CLI installed (optional, can use Cloud Console)

### Step 1: Create Cloud SQL PostgreSQL Database

**Using Cloud Console:**
1. Go to [Cloud SQL Instances](https://console.cloud.google.com/sql/instances)
2. Click **"Create Instance"** → Choose **"PostgreSQL"**
3. Fill in:
   - Instance ID: `logistics-db`
   - Root password: Set a strong password (save it!)
   - Region: `us-central1` (or your preferred)
   - Machine type: `db-f1-micro` (free tier eligible)
4. Click **"Create Instance"** (takes 5-10 minutes)

**Create Database and User:**
1. Go to Cloud SQL → Your instance
2. **Databases** tab → **"Create database"** → Name: `logistics_db`
3. **Users** tab → **"Add user account"** → Username: `logistics_user`, set password

**Run Schema:**
1. Go to Cloud SQL → Your instance → **"SQL Editor"**
2. Select database: `logistics_db`
3. Copy contents of `infra/logistics_db.sql` and paste
4. Click **"Run"**

### Step 2: Create Cloud Storage Bucket (Optional)

**Using Cloud Console:**
1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click **"Create Bucket"**
3. Name: `your-project-logistics-bucket` (globally unique)
4. Location: Same region as Cloud SQL
5. Click **"Create"**

### Step 3: Deploy to Cloud Run

**Using Cloud Console:**
1. Go to [Cloud Run](https://console.cloud.google.com/run)
2. Click **"Create Service"**
3. Select **"Deploy from source repository"** or **"Deploy from container image"**
4. **Service settings**:
   - Service name: `logistics-api`
   - Region: Same as Cloud SQL
   - Authentication: **"Allow unauthenticated invocations"**
5. **Container settings**: Container port: `8080`
6. **Variables & Secrets** tab - Add environment variables:
   ```
   INSTANCE_CONNECTION_NAME=your-project:us-central1:logistics-db
   DB_USER=logistics_user
   DB_PASSWORD=your-password
   DB_NAME=logistics_db
   DB_TABLE_NAME=logistics_documents
   DB_MODEL_NAME=model_log
   OPENAI_API_KEY=sk-your-openai-key
   GCS_BUCKET_NAME=your-project-logistics-bucket
   GCS_MAKE_PUBLIC=false
   PORT=8080
   ```
7. **Connections** tab:
   - Check **"Cloud SQL connections"**
   - Select instance: `logistics-db`
8. Click **"Create"** (deployment takes 2-5 minutes)

**Using gcloud CLI:**
```bash
gcloud run deploy logistics-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances your-project:us-central1:logistics-db \
  --set-env-vars "INSTANCE_CONNECTION_NAME=your-project:us-central1:logistics-db,DB_USER=logistics_user,DB_PASSWORD=your-password,DB_NAME=logistics_db,DB_TABLE_NAME=logistics_documents,DB_MODEL_NAME=model_log,OPENAI_API_KEY=sk-your-key,GCS_BUCKET_NAME=your-bucket"
```

### Step 4: Get Service URL

After deployment, Cloud Run shows:
- **Service URL**: `https://logistics-api-xxxxx.run.app`

Test it:
```bash
curl https://logistics-api-xxxxx.run.app/api/v1/health
# Should return: {"status":"ok","database":"connected","model_log_db":"connected","bucket":"connected"}
```

## Docker

Build and run locally:
```bash
docker build -t logistics-app .
docker run -p 8080:8080 --env-file .env logistics-app
```

## Troubleshooting

### Database Connection Issues
- Verify `INSTANCE_CONNECTION_NAME` format: `project:region:instance`
- Check Cloud SQL connection is enabled in Cloud Run
- Verify user/password are correct
- Ensure both tables exist in the database

### Model Log Table Issues
- Verify `DB_MODEL_NAME` environment variable matches table name
- Check that `model_log` table was created from schema
- Health endpoint will show "disconnected" if table doesn't exist

### Build Fails
- Check Dockerfile is in root directory
- Verify `requirements.txt` exists
- Check build logs in Cloud Build console

### Storage Issues
- Verify bucket name is correct
- Check service account has Storage permissions
- Bucket must exist before deployment

## Environment Variables Summary

**Required:**
- `OPENAI_API_KEY` - For document processing
- Database credentials: Either `INSTANCE_CONNECTION_NAME` OR (`DB_HOST` + `DB_PORT` + `DB_USER` + `DB_PASSWORD` + `DB_NAME`)

**Optional:**
- `DB_TABLE_NAME` - Defaults to `logistics_documents`
- `DB_MODEL_NAME` - Defaults to `model_log`
- `GCS_BUCKET_NAME` - If not set, PDFs won't be uploaded to Cloud Storage
- `GCS_MAKE_PUBLIC` - Defaults to `false`
- `GOOGLE_APPLICATION_CREDENTIALS` - Only needed for local development
- `PORT` - Defaults to `8080`
