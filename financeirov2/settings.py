from pathlib import Path
import os
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv

# ==============================================================================
# BASE
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.getenv("DJANGO_ENV", "production").lower()

# ==============================================================================
# ENV FILES (local only)
# ==============================================================================

if ENVIRONMENT == "development":
    env_file = BASE_DIR / ".env.development"
elif ENVIRONMENT == "production":
    env_file = BASE_DIR / ".env.production"
else:
    env_file = None

if env_file and env_file.exists():
    load_dotenv(env_file, encoding="utf-8")

# ==============================================================================
# CORE SETTINGS
# ==============================================================================

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"

# ------------------------------------------------------------------------------
# Twilio / Finance bot configuration
# - `TWILIO_ALLOWED_NUMBERS` should contain international phone numbers
#   (no 'whatsapp:' prefix) allowed to register expenses via the Twilio bot.
# - `FINANCE_BOT_USER_ID` is the numeric id of the user that will be used
#   as owner/creator for expenses created by the bot.
# You can override these in environment-specific .env files if needed.
TWILIO_ALLOWED_NUMBERS = os.getenv("TWILIO_ALLOWED_NUMBERS")
if TWILIO_ALLOWED_NUMBERS:
    TWILIO_ALLOWED_NUMBERS = [n.strip() for n in TWILIO_ALLOWED_NUMBERS.split(",") if n.strip()]
else:
    TWILIO_ALLOWED_NUMBERS = [
        "+5511999998888",
        "+5521988887777",
    ]

FINANCE_BOT_USER_ID = int(os.getenv("FINANCE_BOT_USER_ID") or 1)

# ==============================================================================
# DATABASE
# ==============================================================================

if ENVIRONMENT == "development":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=60,
            ssl_require=True,
        )
    }

# ==============================================================================
# APPS
# ==============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "core",
    "finance",

    "storages",
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "core.middleware.HouseholdMiddleware",
    "core.middleware.SystemLogMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ==============================================================================
# URLS / TEMPLATES
# ==============================================================================

ROOT_URLCONF = "financeirov2.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "financeirov2.wsgi.application"

# ==============================================================================
# STATIC / MEDIA
# ==============================================================================

if ENVIRONMENT == "production":
    # -------------------------------------------------
    # CSRF
    # -------------------------------------------------
    csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins.split(",") if o.strip()]

    # -------------------------------------------------
    # SUPABASE / S3 CONFIG
    # -------------------------------------------------
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "app-storage")

    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL]):
        raise RuntimeError("Credenciais AWS/S3 não configuradas corretamente.")

    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "sa-east-1")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "path"

    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400"
    }

    # -------------------------------------------------
    # PUBLIC DOMAIN (NO BUCKET HERE)
    # -------------------------------------------------
    SUPABASE_PUBLIC_BASE = os.getenv("SUPABASE_PUBLIC_BASE")  # ex: https://xxxx.supabase.co
    SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")

    if SUPABASE_PUBLIC_BASE:
        public_host = SUPABASE_PUBLIC_BASE.rstrip("/")
    elif SUPABASE_PROJECT_REF:
        public_host = f"https://{SUPABASE_PROJECT_REF}.supabase.co"
    else:
        parsed = urlparse(AWS_S3_ENDPOINT_URL)
        host = parsed.netloc.replace(".storage.supabase.co", ".supabase.co")
        public_host = f"https://{host}"

    PUBLIC_CUSTOM_DOMAIN = public_host.replace("https://", "").replace("http://", "")

    # -------------------------------------------------
    # DJANGO STORAGES
    # -------------------------------------------------
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "region_name": AWS_S3_REGION_NAME,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
                "addressing_style": AWS_S3_ADDRESSING_STYLE,
                "location": "media",
                "file_overwrite": False,
                "default_acl": None,
                "custom_domain": f"{PUBLIC_CUSTOM_DOMAIN}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}",
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "region_name": AWS_S3_REGION_NAME,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
                "addressing_style": AWS_S3_ADDRESSING_STYLE,
                "location": "static",
                "file_overwrite": True,
                "default_acl": None,
                "custom_domain": f"{PUBLIC_CUSTOM_DOMAIN}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}",
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
            },
        },
    }

    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"

    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

else:
    # -------------------------------------------------
    # DEVELOPMENT (LOCAL)
    # -------------------------------------------------
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"

    STATICFILES_DIRS = [BASE_DIR / "core/static/static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

# ==============================================================================
# LOGGING (optional, safe default)
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
}
