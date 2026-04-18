FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/generated:/app

COPY services/notifications/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/notifications/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD pgrep -f "src/main.py" > /dev/null || exit 1

CMD ["python", "src/main.py"]
