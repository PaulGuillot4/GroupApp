#!/usr/bin/env python
"""Smoke test: validates 7 services respond to Healthcheck and Kafka has the 3 topics."""
import subprocess
import sys
import urllib.request
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Insert generated dir first so bare `import common_pb2` in the grpc stubs resolves
GENERATED = str(ROOT / "services" / "gateway" / "generated")
sys.path.insert(0, GENERATED)
sys.path.insert(0, str(ROOT / "services" / "gateway"))

try:
    from generated import (
        auth_pb2_grpc, users_pb2_grpc, groups_pb2_grpc,
        messaging_pb2_grpc, files_pb2_grpc, common_pb2,
    )
    import grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: grpc stubs not importable: {e}")
    GRPC_AVAILABLE = False

GRPC_SERVICES = [
    ("auth",      50051, lambda: auth_pb2_grpc.AuthServiceStub),
    ("users",     50052, lambda: users_pb2_grpc.UsersServiceStub),
    ("groups",    50053, lambda: groups_pb2_grpc.GroupsServiceStub),
    ("messaging", 50054, lambda: messaging_pb2_grpc.MessagingServiceStub),
    ("files",     50055, lambda: files_pb2_grpc.FilesServiceStub),
]

EXPECTED_TOPICS = {"messages.sent", "messages.read", "presence.changed"}


def check_grpc():
    if not GRPC_AVAILABLE:
        print("SKIP gRPC checks (grpcio not installed locally)")
        return []
    failures = []
    for name, port, stub_factory in GRPC_SERVICES:
        try:
            channel = grpc.insecure_channel(f"localhost:{port}")
            stub = stub_factory()(channel)
            resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=5)
            if resp.service != name or resp.status != "OK":
                failures.append(f"{name}: unexpected response service={resp.service} status={resp.status}")
            else:
                print(f"OK  gRPC {name} @ :{port}")
        except Exception as e:
            failures.append(f"{name} @ :{port}: {e}")
    return failures


def check_gateway():
    try:
        with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as r:
            body = json.loads(r.read())
        if body != {"service": "gateway", "status": "OK"}:
            return [f"gateway: unexpected body {body}"]
        print("OK  HTTP gateway @ :8000/health")
        return []
    except Exception as e:
        return [f"gateway: {e}"]


def check_kafka_topics():
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "kafka",
             "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            # Try alternate command name
            out = subprocess.run(
                ["docker", "compose", "exec", "-T", "kafka",
                 "kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--list"],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
        actual = set(line.strip() for line in out.stdout.strip().splitlines() if line.strip())
        missing = EXPECTED_TOPICS - actual
        if missing:
            return [f"kafka: missing topics {missing}. Found: {actual}"]
        print(f"OK  Kafka topics: {sorted(EXPECTED_TOPICS)}")
        return []
    except Exception as e:
        return [f"kafka: {e}"]


def main():
    print("=== GroupsApp Microservices Smoke Test ===")
    failures = []
    failures += check_grpc()
    failures += check_gateway()
    failures += check_kafka_topics()

    print()
    if failures:
        print("--- FAILURES ---", file=sys.stderr)
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        sys.exit(1)
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
