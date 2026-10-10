from datetime import timedelta
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from . import env
from .unfold import UNFOLD  # noqa: F401  (read by django-unfold)

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
    "modeltranslation",  # before admin: it patches the admin of translated models
    "unfold",  # before admin: it replaces the admin templates
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
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
    "api.usage",
    "api.laya",
    "api.insights",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "api.common.middleware.ApiLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "api.common.demo_login.context",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "users.Subscriber"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- database, cache, queue --------------------------------------------------

# SQLite by default, here and in Docker; DATABASE_URL may point at PostgreSQL instead.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60, conn_health_checks=True
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # SQLite has no row locks, so `select_for_update` does nothing on it. Taking
    # the write lock when a transaction begins does the same job for the wallet:
    # two requests cannot both read a balance and then both write it. WAL lets
    # readers carry on meanwhile; a writer waits up to `timeout` for its turn.
    DATABASES["default"]["OPTIONS"] = {
        "transaction_mode": "IMMEDIATE",
        "timeout": 20,
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
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
    "refresh-personal-offers": {
        "task": "api.usage.tasks.refresh_offers",
        "schedule": timedelta(minutes=15),
    },
    "refresh-subscriber-insights": {
        "task": "api.usage.tasks.refresh_insights",
        "schedule": timedelta(hours=1),
    },
    "detect-insights": {
        "task": "api.insights.tasks.detect_insights",
        "schedule": crontab(hour=3, minute=0),  # nightly, Asia/Baku
    },
    "purge-idempotency-keys": {
        "task": "api.billing.tasks.purge_idempotency_keys",
        "schedule": timedelta(hours=1),
    },
}
IDEMPOTENCY_KEY_DAYS = env.number("IDEMPOTENCY_KEY_DAYS", 7)

# Insights are not delivered between these hours (Asia/Baku): from 23:00 to 08:00.
INSIGHTS_QUIET_HOURS = (23, 8) if env.flag("INSIGHTS_QUIET_HOURS", True) else None

# --- language and time -------------------------------------------------------

LANGUAGE_CODE = "en"
LANGUAGES = [("az", _("Azerbaijani")), ("en", _("English"))]
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

# While DEMO_AUTH is on, requests without an Authorization header act as the
# seeded demo subscriber.
# On by default for the demo deployment: it lets anyone use that account.
# Set DEMO_AUTH=false to require a token.
DEMO_AUTH = env.flag("DEMO_AUTH", True)
DEMO_MSISDN = env.text("DEMO_MSISDN", "994516643342")

# Sign-in (users/otp/*). No SMS provider yet: every code is OTP_TEST_CODE.
OTP_TEST_CODE = env.text("OTP_TEST_CODE", "000000")
OTP_TTL = 300  # seconds a sign-in request lives
# Seconds before the same number may ask again; 0 switches the wait off (demos).
OTP_RESEND_AFTER = env.number("OTP_RESEND_AFTER", 60)
OTP_ATTEMPTS = 5  # wrong codes allowed per request
# One-click admin sign-in as each seeded staff account, no password (api/common/demo_login.py).
DEMO_ADMIN_LOGIN = env.flag("DEMO_ADMIN_LOGIN", False)

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
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
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
        "`Accept-Language` (`az`, `en`)."
    ),
    "ENUM_NAME_OVERRIDES": {"LayaLanguageEnum": ["az", "en"]},
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
        {"name": "usage", "description": "30-day usage profile, recommendations, personal offers"},
        {
            "name": "laya",
            "description": "Laya, the voice assistant: plan a task, narrate an insight",
        },
        {
            "name": "insights",
            "description": "What the usage shows, with priced offers; tariff advisor",
        },
        {"name": "sim", "description": "Line, roaming, SMS, PUK, eSIM and paid services"},
        {"name": "billing", "description": "Balance, top-ups, cards and Steam"},
        {"name": "health", "description": "Liveness and readiness probes"},
    ],
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "docExpansion": "none"},
}

# Google Pay: payment_token == "simulated" completes immediately when enabled.
GOOGLE_PAY_SIMULATED = env.flag("GOOGLE_PAY_SIMULATED", DEBUG)

# The assistant: Gemini routes, retrieves and writes when GEMINI_API_KEY is set, keyword rules otherwise.
GEMINI_API_KEY = env.text("GEMINI_API_KEY")
GEMINI_MODEL = env.text("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_STT_MODEL = env.text("GEMINI_STT_MODEL", "gemini-3.1-flash-lite")
GEMINI_TTS_MODEL = env.text("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
GEMINI_EMBED_MODEL = env.text("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_VOICE = env.text("GEMINI_VOICE", "Kore")
# Milvus Lite file by default; set to http://host:19530 for a Milvus server.
MILVUS_URI = env.text("MILVUS_URI", str(BASE_DIR / "data" / "knowledge.db"))
ASSISTANT_RESPONDER = env.text(
    "ASSISTANT_RESPONDER",
    "api.assistant.agent.respond" if GEMINI_API_KEY else "api.assistant.responder.respond",
)
ASSISTANT_RATE_LIMIT = 20  # user messages per minute per subscriber
ASSISTANT_STREAM_DELAY = float(env.text("ASSISTANT_STREAM_DELAY", "0.04"))

# Laya's brain: Gemini when GEMINI_API_KEY is set, else Claude when ANTHROPIC_API_KEY is set, else keyword rules.
ANTHROPIC_API_KEY = env.text("ANTHROPIC_API_KEY")
LAYA_BRAIN = env.text(
    "LAYA_BRAIN",
    "api.laya.gemini"
    if GEMINI_API_KEY
    else "api.laya.claude"
    if ANTHROPIC_API_KEY
    else "api.laya.offline",
)
LAYA_PLAN_MODEL = env.text("LAYA_PLAN_MODEL", "claude-sonnet-5-5")
LAYA_NARRATE_MODEL = env.text("LAYA_NARRATE_MODEL", "claude-haiku-5-5")

# Passwords of the admin accounts `manage.py seed` creates (see README).
SEED_STAFF_PASSWORD = env.text("SEED_STAFF_PASSWORD", "aicell-demo")
