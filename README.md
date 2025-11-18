# Logistics Automation App

A simple logistics document processing application with PDF upload, text extraction, and structured field parsing using OpenAI.

## Features

- ✅ Streamlit UI for PDF document upload
- ✅ PDF text extraction (supports both text-based and scanned PDFs with OCR)
- ✅ OpenAI API integration for structured field extraction and document validation
- ✅ Structured database columns for extracted fields
- ✅ GCP Cloud Storage integration for storing original PDF documents
- ✅ FastAPI backend deployed on Cloud Run
- ✅ PostgreSQL Cloud SQL for data storage
- ✅ Deduplication logic to prevent duplicate records
- ✅ Two-step workflow: Extract & Review → Save
- ✅ Database viewing page in Streamlit

## Project Structure

```
autologistics/
├── app/                    # FastAPI backend
│   ├── main.py            # FastAPI application entry point
│   ├── router.py          # API routes (/extract, /save, /documents)
│   ├── processor.py       # PDF processing and OpenAI integration
│   ├── db.py              # Database connection and operations
│   ├── storage.py         # GCP Cloud Storage integration
│   └── schemas.py         # Pydantic models
├── streamlit_app/         # Streamlit frontend
│   ├── app.py             # Main upload UI
│   └── pages/
│       └── database_check.py  # Database viewing page
├── infra/                 # Infrastructure
│   └── schema.sql         # PostgreSQL schema
├── notebooks/             # Exploration notebooks
│   └── explore_document_processing.ipynb
├── Dockerfile             # Docker configuration
├── requirements.txt       # Python dependencies
└── README.md
```

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

# GCP Cloud Storage (Optional)
GCS_BUCKET_NAME=your-bucket-name
GCS_MAKE_PUBLIC=false
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# OpenAI API (Required)
OPENAI_API_KEY=sk-your-openai-api-key

# API Configuration
API_BASE_URL=http://localhost:8080/api/v1
PORT=8080
```

### 3. Database Setup

The app checks database connection but does not create tables. Run the schema manually:

```bash
psql -U postgres -d logistics_db -f infra/schema.sql
```

Or use Cloud SQL Admin SQL Editor if using Cloud SQL.

### 4. Run Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 5. Run Streamlit Frontend

In another terminal:

```bash
streamlit run streamlit_app/app.py
```

The Streamlit app will be available at `http://localhost:8501`

## Database Schema

The database uses structured columns for extracted fields:

- `tracking_number`, `shipper_name`, `shipper_address`
- `receiver_name`, `receiver_address`
- `carrier`, `shipping_method`, `status`
- `shipment_date`, `delivery_date` (DATE type)
- `weight`, `dimensions`
- `storage_url` - Link to PDF in GCP Cloud Storage
- `additional_data` - JSONB for flexible additional fields
- `created_at`, `updated_at` - Timestamps

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
3. Copy contents of `infra/schema.sql` and paste
4. Click **"Run"**

### Step 2: Create Cloud Storage Bucket (Optional)

**Using Cloud Console:**
1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click **"Create Bucket"**
3. Name: `your-project-logistics-bucket` (globally unique)
4. Location: Same region as Cloud SQL
5. Click **"Create"**

### Step 3: Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/autologistics.git
git push -u origin main
```

### Step 4: Deploy to Cloud Run

**Using Cloud Console:**
1. Go to [Cloud Run](https://console.cloud.google.com/run)
2. Click **"Create Service"**
3. Select **"Deploy from source repository"**
4. **Connect repository**: Choose GitHub, authenticate, select your repo
5. **Build settings**:
   - Build type: **"Dockerfile"**
   - Dockerfile path: `Dockerfile`
   - Build location: `us-central1`
6. **Service settings**:
   - Service name: `logistics-api`
   - Region: Same as Cloud SQL
   - Authentication: **"Allow unauthenticated invocations"**
7. **Container settings**: Container port: `8080`
8. **Variables & Secrets** tab - Add environment variables:
   ```
   INSTANCE_CONNECTION_NAME=your-project:us-central1:logistics-db
   DB_USER=logistics_user
   DB_PASSWORD=your-password
   DB_NAME=logistics_db
   OPENAI_API_KEY=sk-your-openai-key
   GCS_BUCKET_NAME=your-project-logistics-bucket
   GCS_MAKE_PUBLIC=false
   PORT=8080
   ```
9. **Connections** tab:
   - Check **"Cloud SQL connections"**
   - Select instance: `logistics-db`
10. Click **"Create"** (deployment takes 2-5 minutes)

**Using gcloud CLI:**
```bash
gcloud run deploy logistics-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances your-project:us-central1:logistics-db \
  --set-env-vars "INSTANCE_CONNECTION_NAME=your-project:us-central1:logistics-db,DB_USER=logistics_user,DB_PASSWORD=your-password,DB_NAME=logistics_db,OPENAI_API_KEY=sk-your-key,GCS_BUCKET_NAME=your-bucket"
```

### Step 5: Get Service URL

After deployment, Cloud Run shows:
- **Service URL**: `https://logistics-api-xxxxx.run.app`

Test it:
```bash
curl https://logistics-api-xxxxx.run.app/api/v1/health
# Should return: {"status":"ok","database":"connected"}
```

### Step 6: Connect Streamlit to Cloud Run

Update your `.env` file (or set environment variable):
```env
API_BASE_URL=https://logistics-api-xxxxx.run.app/api/v1
```

Then run Streamlit locally:
```bash
streamlit run streamlit_app/app.py
```

### Step 7: Enable Automatic Deployments (Optional)

1. Cloud Run → Your service → **"Revisions"** tab
2. Click **"Manage Continuous Deployment"**
3. Select GitHub repository and branch
4. Enable **"Automatic deployments"**

Every push to your branch will automatically trigger a new deployment.

## Docker

Build and run locally:
```bash
docker build -t logistics-app .
docker run -p 8080:8080 --env-file .env logistics-app
```

## API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/extract` - Extract document (returns preview, doesn't save)
- `POST /api/v1/save` - Save extracted document to database
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get document details

## Troubleshooting

### Database Connection Issues
- Verify `INSTANCE_CONNECTION_NAME` format: `project:region:instance`
- Check Cloud SQL connection is enabled in Cloud Run
- Verify user/password are correct

### Build Fails
- Check Dockerfile is in root directory
- Verify `requirements.txt` exists
- Check build logs in Cloud Build console

### Storage Issues
- Verify bucket name is correct
- Check service account has Storage permissions
- Bucket must exist before deployment

### Streamlit Connection Issues
- Verify `API_BASE_URL` in `.env` matches your Cloud Run URL
- Check CORS is enabled in FastAPI (already configured)
- Ensure Cloud Run service allows unauthenticated invocations

## Environment Variables Summary

**Required:**
- `OPENAI_API_KEY` - For document processing
- Database credentials: Either `INSTANCE_CONNECTION_NAME` OR (`DB_HOST` + `DB_PORT` + `DB_USER` + `DB_PASSWORD` + `DB_NAME`)

**Optional:**
- `GCS_BUCKET_NAME` - If not set, PDFs won't be uploaded to Cloud Storage
- `GCS_MAKE_PUBLIC` - Defaults to `false`
- `GOOGLE_APPLICATION_CREDENTIALS` - Only needed for local development
- `PORT` - Defaults to `8080`
- `API_BASE_URL` - Only needed if Streamlit app is on different host/port
