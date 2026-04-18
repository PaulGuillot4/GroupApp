FROM python:3.11-slim

WORKDIR /app

COPY services/groups/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/groups/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50053
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import groups_pb2_grpc, common_pb2; c=grpc.insecure_channel('localhost:50053'); s=groups_pb2_grpc.GroupsServiceStub(c); s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "src/main.py"]
