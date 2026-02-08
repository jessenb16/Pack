# Pack backend - production image for Lightsail
FROM python:3.11-slim

WORKDIR /app

# System deps: poppler-utils required by pdf2image for PDF thumbnails
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

EXPOSE 8000

# Run uvicorn (no --reload in production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
