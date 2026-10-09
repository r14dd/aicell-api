from datetime import timedelta
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
    "modeltranslation",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "api.common",
    "api.users",
    "api.billing",
    "api.tariffs",
    "api.packs",
    "api.kredit",
    "api.sim",
    "api.content",
    "api.referral",
    "api.assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "api.common.middleware.ApiLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "users.Subscriber"

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
CELERY_BEAT_SCHEDULE = {
    "expire-pack-activations": {
        "task": "api.packs.tasks.expire_activations",
        "schedule": timedelta(minutes=1),
    },
    "purge-idempotency-keys": {
        "task": "api.billing.tasks.purge_idempotency_keys",
        "schedule": timedelta(hours=1),
    },
}
IDEMPOTENCY_KEY_DAYS = env.number("IDEMPOTENCY_KEY_DAYS", 7)

# --- language and time -------------------------------------------------------

LANGUAGE_CODE = "en"
LANGUAGES = [("az", _("Azerbaijani")), ("ru", _("Russian")), ("en", _("English"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
MODELTRANSLATION_FALLBACK_LANGUAGES = ("en",)
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
CSRF_TRUSTED_ORIGINS = env.items("CSRF_TRUSTED_ORIGINS")

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
    SESSION_COOKIE_SECURE = env.flag("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env.flag("SECURE_COOKIES", True)

# --- API ----------------------------------------------------------------------

# The app has no login screen yet (users/otp/* is :todo). While DEMO_AUTH is on,
# requests without an Authorization header act as the seeded demo subscriber.
# Off unless switched on deliberately: it lets anyone use that account.
DEMO_AUTH = env.flag("DEMO_AUTH", False)
DEMO_MSISDN = env.text("DEMO_MSISDN", "994516643342")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.common.auth.BearerAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "api.common.auth.DemoAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "api.common.exceptions.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "api.common.schema.AutoSchema",
}

# Requests per period; an empty value switches a limit off.
THROTTLE_RATES = {
    "otp_ip": env.rate("THROTTLE_OTP_IP", "5/min"),
    "otp_phone": env.rate("THROTTLE_OTP_PHONE", "5/min"),
    "money": env.rate("THROTTLE_MONEY", "30/min"),
    "subscriber": env.rate("THROTTLE_SUBSCRIBER", "300/min"),
}

SIMPLE_JWT = {
    # token/refresh/ is :todo, so the prototype access token is long-lived.
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "aicell API",
    "VERSION": "0.1.0",
    "DESCRIPTION": (
        "Backend of the aicell mobile app.\n\n"
        "**Authorize** with `Bearer <access-jwt>`.\n\n"
        "Endpoints marked `:todo` are routed at their final path and answer "
        "`501 not_implemented`. Copy comes back in the language of "
        "`Accept-Language` (`az`, `ru`, `en`)."
    ),
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SERVE_AUTHENTICATION": [],
    "COMPONENT_SPLIT_REQUEST": True,
    "AUTHENTICATION_WHITELIST": [
        "api.common.auth.BearerAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "SORT_OPERATIONS": False,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "TAGS": [
        {"name": "users", "description": "Sign in and the subscriber's profile"},
        {"name": "tariffs", "description": "Tariff catalogue and the subscriber's tariff"},
        {"name": "packs", "description": "Internet, social and roaming packs"},
        {"name": "kredit", "description": "Credit products and the open debt"},
        {
            "name": "content",
            "description": "Home feed, stories, notifications, lottery, games and offers",
        },
        {"name": "referral", "description": "Invite & earn"},
        {"name": "assistant", "description": "Support inbox and the chat assistant"},
        {"name": "sim", "description": "Line, roaming, SMS, PUK, eSIM and paid services"},
        {"name": "billing", "description": "Balance, top-ups, cards and Steam"},
        {"name": "health", "description": "Liveness and readiness probes"},
    ],
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "docExpansion": "none"},
}

# Google Pay: payment_token == "simulated" completes immediately when enabled.
GOOGLE_PAY_SIMULATED = env.flag("GOOGLE_PAY_SIMULATED", DEBUG)

ASSISTANT_RESPONDER = env.text("ASSISTANT_RESPONDER", "api.assistant.responder.respond")
ASSISTANT_RATE_LIMIT = 20  # user messages per minute per subscriber
ASSISTANT_STREAM_DELAY = float(env.text("ASSISTANT_STREAM_DELAY", "0.04"))

# Passwords of the admin accounts `manage.py seed` creates (see README).
SEED_STAFF_PASSWORD = env.text("SEED_STAFF_PASSWORD", "aicell-demo")
