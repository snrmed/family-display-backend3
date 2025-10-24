# Use a Python base image with necessary system tools
FROM python:3.11-slim

# Install system dependencies required for Pillow (image manipulation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and the fonts
# Copies backend/app.py, backend/generator.py, and backend/fonts/
COPY backend /app/backend

# Set the PORT environment variable for the composer service
ENV PORT 8080

# Expose the port
EXPOSE 8080

# Default command runs the Flask composer service
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "backend.app:app"]
