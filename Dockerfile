# ---- Base ----
FROM python:3.11-slim

# System deps for headless Chromium (expanded list)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git ca-certificates \
    fonts-liberation fonts-noto-color-emoji \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libxkbcommon0 \
    libnss3 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgtk-3-0 libgbm1 \
    libx11-6 libx11-xcb1 libxcb1 libxext6 \
    libxrender1 libxtst6 libxi6 libpango-1.0-0 \
    libcairo2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# avoid playwright trying to download at pip time
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# install browser
RUN playwright install --with-deps chromium || playwright install chromium

# copy the rest
COPY . /app

# run from backend/
WORKDIR /app/backend

ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
