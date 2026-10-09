from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from . import env

BASE_DIR = Path(__file__).resolve().parent.parent
env.load_dotenv(BASE_DIR / ".env")

# --- core -------------------------------------------------------------------

DEBUG = env.flag("DJANGO_DEBUG", False)

SECRET_KEY = env.text("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")
    SECRET_KEY = "dev-only-insecure-key-never-used-outside-local-debug-runs"

ALLOWED_HOSTS = env.items("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- database, cache, queue --------------------------------------------------

# PostgreSQL when DATABASE_URL is set (Docker), SQLite for a plain local run.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60, conn_health_checks=True
    )
}

REDIS_URL = env.text("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "aicell",
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CATALOGUE_CACHE_SECONDS = env.number("CATALOGUE_CACHE_SECONDS", 300)

CELERY_BROKER_URL = env.text("CELERY_BROKER_URL", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL  # no broker: run tasks inline
CELERY_TIMEZONE = "Asia/Baku"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {}

# --- language and time -------------------------------------------------------

LANGUAGE_CODE = "en"
LANGUAGES = [("az", _("Azerbaijani")), ("ru", _("Russian")), ("en", _("English"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Baku"
USE_I18N = True
USE_TZ = True

# --- static and media --------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- security ----------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.items("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "idempotency-key",
    "x-app-version",
    "x-platform",
]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    # Behind a TLS-terminating proxy that sets X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.flag("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health/"]  # container healthchecks speak plain HTTP
    SECURE_HSTS_SECONDS = env.number("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# --- API ----------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "aicell API",
    "VERSION": "0.1.0",
    "DESCRIPTION": "Backend of the aicell mobile app.",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/",
}
