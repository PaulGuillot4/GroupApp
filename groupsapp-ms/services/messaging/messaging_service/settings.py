import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "channels",
]

ASGI_APPLICATION = "messaging_service.asgi.application"

_redis_url = os.getenv("REDIS_URL", "")

if _redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_redis_url],
            },
        }
    }
else:
    # Fallback for tests or single-instance dev
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# Minimal dummy DB — Django requires DATABASES but we use MongoDB directly
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
