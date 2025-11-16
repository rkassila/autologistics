# Dockerfile for FastAPI backend (Cloud Run deployment)

FROM python:3.11-slim

# Install system dependencies for PDF processing and OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run FastAPI with uvicorn
# Cloud Run sets PORT environment variable automatically
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
