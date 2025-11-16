# Quick Deployment Steps for Cloud Run

## Prerequisites
- Google Cloud Project created
- Billing enabled
- `gcloud` CLI installed (optional, can use Cloud Console)

## Step 1: Create Cloud SQL PostgreSQL Database

### Option A: Using Cloud Console (Easiest)
1. Go to [Cloud SQL Instances](https://console.cloud.google.com/sql/instances)
2. Click **"Create Instance"**
3. Choose **"PostgreSQL"**
4. Fill in:
   - **Instance ID**: `logistics-db`
   - **Root password**: Set a strong password (save it!)
   - **Region**: Choose closest to you (e.g., `us-central1`)
   - **Machine type**: `db-f1-micro` (free tier eligible)
5. Click **"Create Instance"** (takes 5-10 minutes)

### Option B: Using gcloud CLI
```bash
gcloud sql instances create logistics-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=YOUR_ROOT_PASSWORD
```

### Create Database and User
Once instance is created:

**Using Cloud SQL Admin (easiest):**
1. Go to Cloud SQL → Your instance
2. Click **"Databases"** tab → **"Create database"**
   - Name: `logistics_db`
3. Click **"Users"** tab → **"Add user account"**
   - Username: `logistics_user`
   - Password: (set password)

**Or using gcloud:**
```bash
# Create database
gcloud sql databases create logistics_db --instance=logistics-db

# Create user
gcloud sql users create logistics_user \
  --instance=logistics-db \
  --password=YOUR_PASSWORD
```

### Run Schema
1. Go to Cloud SQL → Your instance → **"SQL Editor"**
2. Select database: `logistics_db`
3. Copy contents of `infra/schema.sql` and paste
4. Click **"Run"**

**Or using psql (if you have Cloud SQL Proxy):**
```bash
# Get connection name
INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe logistics-db --format="value(connectionName)")

# Connect via Cloud SQL Proxy (in another terminal)
./cloud_sql_proxy -instances=$INSTANCE_CONNECTION_NAME=tcp:5432

# In another terminal, run schema
psql -h localhost -U postgres -d logistics_db -f infra/schema.sql
```

## Step 2: Create Cloud Storage Bucket (Optional but Recommended)

### Using Cloud Console
1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click **"Create Bucket"**
3. Fill in:
   - **Name**: `your-project-logistics-bucket` (must be globally unique)
   - **Location type**: `Region`
   - **Region**: Same as Cloud SQL (e.g., `us-central1`)
4. Click **"Create"**

### Using gcloud CLI
```bash
gsutil mb -l us-central1 gs://your-project-logistics-bucket
```

### Set Permissions (if needed)
The default service account used by Cloud Run should have access automatically.

## Step 3: Push Code to GitHub

```bash
# Initialize git (if not already)
git init

# Add files
git add .

# Commit
git commit -m "Initial commit"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/autologistics.git

# Push
git push -u origin main
```

## Step 4: Deploy to Cloud Run from GitHub

### Option A: First-time Setup via Cloud Console
1. Go to [Cloud Run](https://console.cloud.google.com/run)
2. Click **"Create Service"**
3. Select **"Deploy from source repository"**
4. **Connect repository**:
   - Choose **"GitHub"**
   - Authenticate GitHub if needed
   - Select your repository: `YOUR_USERNAME/autologistics`
   - Select branch: `main` (or `master`)
5. **Build settings**:
   - Build type: **"Dockerfile"**
   - Dockerfile path: `Dockerfile` (if in root, leave default)
   - Build location: `us-central1` (or your preferred region)
6. **Service settings**:
   - Service name: `logistics-api`
   - Region: Same as your Cloud SQL
   - Authentication: **"Allow unauthenticated invocations"** (for testing)
7. **Container settings**:
   - Container port: `8080`
8. **Variables & Secrets** (click "Variables and Secrets" tab):
   Add these environment variables:
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

### Option B: Using gcloud CLI
```bash
# Build and deploy
gcloud run deploy logistics-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances your-project:us-central1:logistics-db \
  --set-env-vars "INSTANCE_CONNECTION_NAME=your-project:us-central1:logistics-db,DB_USER=logistics_user,DB_PASSWORD=your-password,DB_NAME=logistics_db,OPENAI_API_KEY=sk-your-key,GCS_BUCKET_NAME=your-bucket"
```

## Step 5: Get Your Service URL

After deployment, Cloud Run will show:
- **Service URL**: `https://logistics-api-xxxxx.run.app`

Test it:
```bash
curl https://logistics-api-xxxxx.run.app/api/v1/health
```

## Step 6: Enable Automatic Deployments (Optional)

1. Go to Cloud Run → Your service
2. Go to **"Revisions"** tab
3. Click **"Manage Continuous Deployment"**
4. Select your GitHub repository and branch
5. Enable **"Automatic deployments"**

Now, every push to your branch will automatically trigger a new deployment!

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

## Environment Variables Summary

```env
# Required
INSTANCE_CONNECTION_NAME=project-id:region:instance-name
DB_USER=logistics_user
DB_PASSWORD=your-password
DB_NAME=logistics_db
OPENAI_API_KEY=sk-your-key

# Optional
GCS_BUCKET_NAME=your-bucket-name
GCS_MAKE_PUBLIC=false
PORT=8080
```

## Quick Test

```bash
# Health check
curl https://YOUR-SERVICE-URL/api/v1/health

# Should return:
# {"status":"ok","database":"connected"}
```

Done! Your API is now live on Cloud Run. 🚀
