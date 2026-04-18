FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/generated:/app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/auth/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50051
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import auth_pb2_grpc, common_pb2; c=grpc.insecure_channel('localhost:50051'); s=auth_pb2_grpc.AuthServiceStub(c); s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "grpc_server.py"]
