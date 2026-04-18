FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/generated:/app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/messaging/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/messaging/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50054 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import grpc; from generated import messaging_pb2_grpc, common_pb2; c=grpc.insecure_channel('localhost:50054'); s=messaging_pb2_grpc.MessagingServiceStub(c); s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "grpc_server.py"]
