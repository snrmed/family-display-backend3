# ── Dockerfile (at repo root) ────────────────────────────────────────────────
FROM python:3.11-slim

# System deps (Pillow works best with JPEG/zlib present)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libjpeg62-turbo-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the backend app (includes web/designer when you add it)
COPY backend/ ./backend/

# Runtime env
ENV PORT=8080 \
    PYTHONUNBUFFERED=1

# Expose if you run locally (Cloud Run doesn’t require EXPOSE)
EXPOSE 8080

# Use gunicorn to serve Flask app
WORKDIR /app/backend
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]