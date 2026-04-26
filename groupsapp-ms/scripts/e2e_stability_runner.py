#!/usr/bin/env python
"""
Runs smoke + E2E tests consecutively to validate Day 6 stability.

Usage:
    python scripts/e2e_stability_runner.py --runs 5
"""
import argparse
import subprocess
import sys
import time


def run_cmd(cmd: list[str], label: str):
    print(f"\n{'=' * 72}")
    print(f"  {label}")
    print(f"{'=' * 72}")
    print("  >", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def main():
    parser = argparse.ArgumentParser(description="Run smoke + E2E flow multiple times")
    parser.add_argument("--runs", type=int, default=5, help="Required successful consecutive runs")
    parser.add_argument("--gateway", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--ws", default="ws://localhost:8001", help="WebSocket base URL")
    parser.add_argument("--sleep-between", type=float, default=1.5, help="Sleep between runs")
    args = parser.parse_args()

    if args.runs < 1:
        raise ValueError("--runs must be >= 1")

    started = time.time()
    for i in range(1, args.runs + 1):
        print(f"\nRun {i}/{args.runs}")
        run_cmd([sys.executable, "scripts/smoke_test.py"], f"Smoke Test {i}")
        run_cmd(
            [
                sys.executable,
                "scripts/e2e_demo.py",
                "--gateway",
                args.gateway,
                "--ws",
                args.ws,
            ],
            f"E2E Demo {i}",
        )
        if i < args.runs:
            time.sleep(args.sleep_between)

    elapsed = time.time() - started
    print(f"\nSUCCESS: {args.runs}/{args.runs} runs passed in {elapsed:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
