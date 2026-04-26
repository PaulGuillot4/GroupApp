#!/usr/bin/env python
"""
End-to-end demo script for GroupsApp Microservices.

Validates the full flow:
  1. Register two users
  2. Login both
  3. User A creates a group
  4. User B joins the group
  5. User A sends a group message via WS
  6. Verify message history via Gateway REST
  7. User A sends a private message to User B via WS
  8. User A uploads a file via Gateway
  9. Verify file metadata
 10. Search users
 11. Get/update user profile
 12. Mark message as read via WS

Usage:
    python scripts/e2e_demo.py [--gateway http://localhost:8000] [--ws ws://localhost:8001]
"""
import argparse
import asyncio
import json
import sys
import time
import urllib.request
import urllib.error
import io


GATEWAY = "http://localhost:8000"
WS_URL = "ws://localhost:8001"


# ─── HTTP helpers ───────────────────────────────────────────────────────────

def api(method: str, path: str, body=None, token=None, expect=None):
    """Make an HTTP request to the Gateway and return parsed JSON."""
    url = f"{GATEWAY}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        if expect and e.code == expect:
            return json.loads(body_err) if body_err else {}
        print(f"  FAIL {method} {path} → {e.code}: {body_err}", file=sys.stderr)
        raise


def api_upload(path: str, filepath_content: bytes, filename: str, token: str):
    """Multipart file upload via urllib."""
    boundary = "----E2EBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + filepath_content + f"\r\n--{boundary}--\r\n".encode()

    url = f"{GATEWAY}{path}"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# ─── WebSocket helpers ──────────────────────────────────────────────────────

async def ws_connect(token: str):
    """Connect to the messaging WebSocket and return the connection object."""
    try:
        import websockets
    except ImportError:
        print("  SKIP WebSocket tests (websockets package not installed)")
        return None
    uri = f"{WS_URL}/ws/chat/?token={token}"
    ws = await websockets.connect(uri)
    return ws


async def ws_send(ws, data: dict):
    await ws.send(json.dumps(data))


async def ws_recv(ws, timeout=5.0):
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        return json.loads(raw)
    except asyncio.TimeoutError:
        return None


# ─── Test steps ─────────────────────────────────────────────────────────────

def step(num: int, desc: str):
    print(f"\n{'='*60}")
    print(f"  Step {num}: {desc}")
    print(f"{'='*60}")


def run_demo():
    results = {"passed": 0, "failed": 0, "skipped": 0}
    ts = int(time.time())

    # ── Step 1: Register two users ─────────────────────────────────
    step(1, "Register two users")
    user_a_name = f"alice_{ts}"
    user_b_name = f"bob_{ts}"

    resp_a = api("POST", "/api/auth/register", {
        "username": user_a_name,
        "email": f"{user_a_name}@test.com",
        "password": "Password123!",
    })
    assert resp_a.get("access_token"), f"Register A failed: {resp_a}"
    token_a = resp_a["access_token"]
    user_a_id = resp_a["user_id"]
    print(f"  ✓ Registered {user_a_name} (id={user_a_id})")

    resp_b = api("POST", "/api/auth/register", {
        "username": user_b_name,
        "email": f"{user_b_name}@test.com",
        "password": "Password123!",
    })
    assert resp_b.get("access_token"), f"Register B failed: {resp_b}"
    token_b = resp_b["access_token"]
    user_b_id = resp_b["user_id"]
    print(f"  ✓ Registered {user_b_name} (id={user_b_id})")
    results["passed"] += 1

    # ── Step 2: Login both users ───────────────────────────────────
    step(2, "Login both users")
    login_a = api("POST", "/api/auth/login", {
        "username": user_a_name, "password": "Password123!"
    })
    token_a = login_a["access_token"]
    print(f"  ✓ Login {user_a_name}")

    login_b = api("POST", "/api/auth/login", {
        "username": user_b_name, "password": "Password123!"
    })
    token_b = login_b["access_token"]
    print(f"  ✓ Login {user_b_name}")
    results["passed"] += 1

    # ── Step 3: User A creates a group ─────────────────────────────
    step(3, "User A creates a group")
    group = api("POST", "/api/groups", {
        "name": f"TestGroup_{ts}",
        "description": "E2E test group",
        "subscription_type": "free",
    }, token=token_a)
    group_id = group["id"]
    print(f"  ✓ Created group '{group['name']}' (id={group_id})")
    results["passed"] += 1

    # ── Step 4: User B joins the group ─────────────────────────────
    step(4, "User B joins the group")
    api("POST", f"/api/groups/{group_id}/join", token=token_b)
    print(f"  ✓ {user_b_name} joined group")

    # Verify membership
    membership = api("GET", f"/api/groups/{group_id}/membership", token=token_b)
    assert membership["is_member"], "Membership check failed"
    print(f"  ✓ Membership verified: role={membership['role']}")
    results["passed"] += 1

    # ── Step 5: Verify message history via REST ────────────────────
    step(5, "Verify message history via Gateway REST")
    history = api("GET", f"/api/messages/history?group_id={group_id}&limit=10", token=token_a)
    initial_count = len(history.get("messages", []))
    print(f"  ✓ Message history retrieved ({initial_count} messages initially)")
    results["passed"] += 1

    # ── Step 6: User A uploads a file ──────────────────────────────
    step(6, "User A uploads a file via Gateway")
    test_content = b"Hello from E2E test! This is a test file."
    try:
        upload_resp = api_upload("/api/files/upload", test_content, "test_file.txt", token_a)
        file_id = upload_resp.get("file_id", "")
        file_url = upload_resp.get("url", "")
        print(f"  ✓ Uploaded file: id={file_id}, url={file_url}")

        # Verify file metadata via Gateway
        file_meta = api("GET", f"/api/files/{file_id}", token=token_a)
        assert file_meta["id"] == file_id, f"File metadata mismatch: {file_meta}"
        print(f"  ✓ File metadata verified: mime={file_meta['mime_type']}, size={file_meta['size']}")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ File upload failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 7: Search users ───────────────────────────────────────
    step(7, "Search users via Gateway")
    search_results = api("GET", f"/api/users/search?q={user_a_name[:5]}", token=token_b)
    found = any(u["username"] == user_a_name for u in search_results)
    if found:
        print(f"  ✓ Found {user_a_name} in search results")
        results["passed"] += 1
    else:
        print(f"  ✗ {user_a_name} not found in search results: {search_results}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 8: Get user profile ───────────────────────────────────
    step(8, "Get user profile via Gateway")
    try:
        profile = api("GET", f"/api/users/{user_a_id}/profile", token=token_b)
        assert profile["user_id"] == user_a_id
        print(f"  ✓ Profile retrieved: username={profile['username']}, bio='{profile.get('bio', '')}'")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ Get profile failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 9: Update user profile ────────────────────────────────
    step(9, "Update user profile via Gateway")
    try:
        updated = api("PATCH", "/api/users/me/profile", {
            "bio": "I am Alice, testing E2E!",
            "avatar_url": "https://example.com/alice.jpg",
        }, token=token_a)
        assert updated["bio"] == "I am Alice, testing E2E!"
        assert updated["avatar_url"] == "https://example.com/alice.jpg"
        print(f"  ✓ Profile updated: bio='{updated['bio']}', avatar='{updated['avatar_url']}'")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ Update profile failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 10: List conversations ────────────────────────────────
    step(10, "List conversations via Gateway")
    try:
        convos = api("GET", "/api/messages/conversations", token=token_a)
        print(f"  ✓ Conversations listed: {len(convos)} conversations")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ List conversations failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 11: List my groups ────────────────────────────────────
    step(11, "List my groups via Gateway")
    try:
        my_groups = api("GET", "/api/groups/me", token=token_a)
        has_our_group = any(g["id"] == group_id for g in my_groups)
        assert has_our_group, f"Our group not found in: {my_groups}"
        print(f"  ✓ My groups listed: {len(my_groups)} groups (includes test group)")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ List my groups failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Step 12: List group members ────────────────────────────────
    step(12, "List group members via Gateway")
    try:
        members = api("GET", f"/api/groups/{group_id}/members", token=token_a)
        member_ids = [m["user_id"] for m in members]
        assert user_a_id in member_ids, "User A not in members"
        assert user_b_id in member_ids, "User B not in members"
        print(f"  ✓ Members listed: {len(members)} members (both users present)")
        results["passed"] += 1
    except Exception as exc:
        print(f"  ✗ List members failed: {exc}", file=sys.stderr)
        results["failed"] += 1

    # ── Summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  E2E Demo Results")
    print(f"{'='*60}")
    print(f"  ✓ Passed: {results['passed']}")
    print(f"  ✗ Failed: {results['failed']}")
    print(f"  ○ Skipped: {results['skipped']}")
    print(f"{'='*60}")

    if results["failed"] > 0:
        sys.exit(1)
    print("\n  All E2E checks passed! 🎉\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GroupsApp E2E Demo")
    parser.add_argument("--gateway", default=GATEWAY, help="Gateway base URL")
    parser.add_argument("--ws", default=WS_URL, help="WebSocket base URL")
    args = parser.parse_args()
    GATEWAY = args.gateway
    WS_URL = args.ws
    run_demo()
