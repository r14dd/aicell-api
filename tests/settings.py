"""Settings for the test run: production-like, with nothing read from a developer's `.env`.

`DATABASE_URL` and `REDIS_URL` are taken from the environment when set, which is
how the PostgreSQL and Redis tests are switched on.
"""

import os

os.environ["DJANGO_READ_DOT_ENV"] = "false"
os.environ["DJANGO_DEBUG"] = "false"
os.environ["DJANGO_SECRET_KEY"] = "test-only-secret-key-with-enough-length-for-hs256-signing"
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"
os.environ["SECURE_SSL_REDIRECT"] = "false"
os.environ["DEMO_AUTH"] = "false"
os.environ.setdefault("TEST_REDIS_URL", os.environ.pop("REDIS_URL", ""))

from config.settings import *  # noqa: E402, F403

# The suite runs on the in-memory cache; Redis tests connect to TEST_REDIS_URL themselves.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
TEST_REDIS_URL = os.environ["TEST_REDIS_URL"]
CELERY_TASK_ALWAYS_EAGER = True
LAYA_BRAIN = "api.laya.offline"  # never the network
ASSISTANT_RESPONDER = "api.assistant.responder.respond"  # nor Gemini
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
