FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files at build time
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

# Healthcheck – verify the HTTP server responds
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/admin/login/ || exit 1

# Run with Daphne (ASGI)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
