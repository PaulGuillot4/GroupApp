import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

app = FastAPI(title="Users Service REST")

USERS_BASE_URL = os.getenv("USERS_BASE_URL", "http://localhost:8003")


class UpdateProfileBody(BaseModel):
    avatar_url: str = ""
    bio: str = ""


def _get_engine():
    from src.db import get_engine
    return get_engine()


@app.get("/health")
def health():
    return {"service": "users-rest", "status": "OK"}


@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    """Get a user profile by user_id (public endpoint, called by gateway)."""
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT au.id::text AS user_id,
                   au.username,
                   au.email,
                   COALESCE(up.avatar_url, '') AS avatar_url,
                   COALESCE(up.bio, '') AS bio,
                   up.last_seen
            FROM auth.users au
            LEFT JOIN user_profiles up ON au.id::text = up.user_id
            WHERE au.id::text = :uid
        """), {"uid": user_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    result = {
        "user_id": row.user_id,
        "username": row.username,
        "email": row.email,
        "avatar_url": row.avatar_url,
        "bio": row.bio,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
    }
    return result


@app.patch("/profile")
def update_profile(
    body: UpdateProfileBody,
    x_user_id: str = Header(...),
):
    """Update avatar_url and/or bio for the authenticated user."""
    engine = _get_engine()
    with engine.connect() as conn:
        # Upsert user_profiles row
        conn.execute(text("""
            INSERT INTO user_profiles (user_id, avatar_url, bio)
            VALUES (:uid, :avatar, :bio)
            ON CONFLICT (user_id)
            DO UPDATE SET
                avatar_url = CASE WHEN :avatar != '' THEN :avatar ELSE user_profiles.avatar_url END,
                bio = CASE WHEN :bio != '' THEN :bio ELSE user_profiles.bio END
        """), {"uid": x_user_id, "avatar": body.avatar_url, "bio": body.bio})
        conn.commit()

    # Return updated profile
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT au.id::text AS user_id,
                   au.username,
                   au.email,
                   COALESCE(up.avatar_url, '') AS avatar_url,
                   COALESCE(up.bio, '') AS bio,
                   up.last_seen
            FROM auth.users au
            LEFT JOIN user_profiles up ON au.id::text = up.user_id
            WHERE au.id::text = :uid
        """), {"uid": x_user_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": row.user_id,
        "username": row.username,
        "email": row.email,
        "avatar_url": row.avatar_url,
        "bio": row.bio,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
    }
