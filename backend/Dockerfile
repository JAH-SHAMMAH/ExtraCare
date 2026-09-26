FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directory for SQLite (dev only)
RUN mkdir -p /data

# Migration-on-boot entrypoint (runs `alembic upgrade head` in prod/staging).
# NOTE: this applies to DOCKER deployments only. Fairview's Render backend is not
# built from this Dockerfile, so ENTRYPOINT never runs there and migrations are
# applied separately — see entrypoint.sh's banner and DEPLOYMENT.md §0.
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
