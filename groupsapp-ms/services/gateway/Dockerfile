FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/generated:/app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/gateway/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
