# ---- Base ----
FROM python:3.11-slim

# Avoid interactive tz / font prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install all Chromium dependencies manually (avoiding playwright install-deps)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl wget \
      # Fonts
      fontconfig fonts-liberation fonts-noto-core fonts-dejavu-core \
      # Chromium core dependencies
      libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
      # X11 libraries
      libx11-6 libx11-xcb1 libxcb1 libxcb-dri3-0 libxext6 libxshmfence1 \
      # GTK/GLib
      libgtk-3-0 libglib2.0-0 \
      # Misc
      libexpat1 libuuid1 \
    && rm -rf /var/lib/apt/lists/*

# App root
WORKDIR /app

# Copy and install Python deps first (better layer caching)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright Chromium (browser only, no system deps)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium

# Copy the rest of the project
COPY . /app

# Cloud Run port
ENV PORT=8080

# Start the FastAPI app
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
