# Environment Variables Template

Create a `.env` file in the root directory with the following variables:

```env
# ============================================
# Database Configuration (PostgreSQL)
# ============================================
# For Cloud SQL (Unix socket connection):
INSTANCE_CONNECTION_NAME=project-id:region:instance-name

# For regular PostgreSQL connection:
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-database-password
DB_NAME=logistics_db

# Note: If INSTANCE_CONNECTION_NAME is set, it will use Unix socket connection
# Otherwise, it will use DB_HOST, DB_PORT for TCP connection

# ============================================
# GCP Cloud Storage Configuration
# ============================================
# Required: Name of your GCS bucket for storing PDFs
GCS_BUCKET_NAME=your-bucket-name

# Optional: Set to 'true' to make uploaded files publicly accessible
# Default: 'false' (uses gs:// paths instead)
GCS_MAKE_PUBLIC=false

# For local development: Path to service account JSON key file
# Leave empty if running on Cloud Run (uses default credentials)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# ============================================
# OpenAI API Configuration
# ============================================
# Required: Your OpenAI API key for document parsing
OPENAI_API_KEY=sk-your-openai-api-key-here

# ============================================
# API Configuration
# ============================================
# Optional: Port for FastAPI backend (default: 8080)
PORT=8080

# Optional: Base URL for API (used by Streamlit frontend)
# Default: http://localhost:8080/api/v1
API_BASE_URL=http://localhost:8080/api/v1
```

## Required vs Optional Variables

### Required:
- `OPENAI_API_KEY` - Must be set for document processing
- Database credentials (either `INSTANCE_CONNECTION_NAME` OR `DB_HOST` + `DB_PORT` + `DB_USER` + `DB_PASSWORD` + `DB_NAME`)

### Optional:
- `GCS_BUCKET_NAME` - If not set, PDFs won't be uploaded to Cloud Storage (but processing will still work)
- `GCS_MAKE_PUBLIC` - Defaults to `false`
- `GOOGLE_APPLICATION_CREDENTIALS` - Only needed for local development
- `PORT` - Defaults to `8080`
- `API_BASE_URL` - Only needed if Streamlit app is on different host/port

## Quick Start

1. Copy this template to `.env`:
   ```bash
   cp ENV_TEMPLATE.md .env
   ```

2. Edit `.env` and fill in your values

3. For Cloud Run deployment, set environment variables in Cloud Run console instead of `.env` file
