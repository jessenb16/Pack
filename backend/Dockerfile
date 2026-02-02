# Pack API - production image
FROM python:3.11-slim

# System deps for pdf2image (poppler-utils)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/

EXPOSE 8000

# All config via env at runtime; no secrets in image
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
