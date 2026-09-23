# ==============================================================================
# IceStream - Production FastAPI Backend Container
# ==============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Create non-root system group and user
RUN groupadd -g 10001 icestream && \
    useradd -u 10001 -g icestream -s /bin/bash -m icestream

# Copy application source directories
COPY backend /app/backend
COPY quality-engine /app/quality-engine
COPY schema /app/schema
COPY generator /app/generator
COPY iceberg /app/iceberg

# Set ownership of application directory to non-root user
RUN chown -R icestream:icestream /app

# Environment variables
ENV PYTHONPATH="/app:/app/backend:/app/quality-engine:/app/iceberg"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Drop privileges to non-root user
USER icestream

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
