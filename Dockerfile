# ---- Base ----
FROM python:3.11-slim

# System deps for headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git ca-certificates fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libxkbcommon0 libnss3 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgtk-3-0 libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Chromium for Playwright
RUN python -m playwright install --with-deps chromium

# Copy the repo (we need backend/, including web/layouts/)
COPY . /app

# Run from backend/ where main.py is
WORKDIR /app/backend

# Cloud Run expects the server on $PORT
ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
