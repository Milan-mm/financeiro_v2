from pathlib import Path
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import dj_database_url # Facilita a vida com o Supabase

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 1. CARREGAMENTO DE AMBIENTE (Railway-friendly)
# ==============================================================================

from dotenv import load_dotenv

# Railway NÃO usa arquivos .env em produção
# Tudo vem via variáveis de ambiente do sistema

ENVIRONMENT = os.getenv("DJANGO_ENV", "production").lower()

# financeirov2/settings.py

# ... (código anterior)

ENVIRONMENT = os.getenv("DJANGO_ENV", "production").lower()

if ENVIRONMENT == "development":
    env_file = BASE_DIR / ".env.development"

    if env_file.exists():
        load_dotenv(env_file, encoding="utf-8")
        print("✓ .env.development carregado")
    else:
        print("⚠️ .env.development não encontrado. Usando variáveis do sistema.")
else:
    # ALTERAÇÃO AQUI: Tenta carregar .env.production se existir (útil para testes locais de prod)
    env_file = BASE_DIR / ".env.production"

    if env_file.exists():
        load_dotenv(env_file, encoding="utf-8")
        print("✓ .env.production carregado (Modo Produção Local)")
    else:
        print("🚀 Produção (Railway): usando variáveis de ambiente do sistema")

print("ENVIRONMENT =", ENVIRONMENT)

# ... (restante do código)

# ==============================================================================
# 2. CONFIGURAÇÕES GERAIS
# ==============================================================================

# DEBUG: Em produção deve ser sempre False, mas lemos do env por segurança
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# SECRET_KEY: Obrigatória
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-chave-padrao-dev")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,").split(",")

# ==============================================================================
# 3. BANCO DE DADOS
# ==============================================================================

if ENVIRONMENT == "development":
    print("🔧 Usando banco de dados: SQLite (Local)")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    print("🚀 Usando banco de dados: PostgreSQL (Produção/Supabase)")
    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=60,
            ssl_require=True,  # Supabase normalmente requer SSL

        )
    }
# ==============================================================================
# 4. APPS E MIDDLEWARE
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core', # Seu app principal
    "storages",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware", # Essencial para CSS no Railway
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.HouseholdMiddleware',
    'core.middleware.SystemLogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'financeirov2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'financeirov2.wsgi.application'

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"

# ==============================================================================
# 5. ARQUIVOS ESTÁTICOS (CSS/JS)
# ==============================================================================

if ENVIRONMENT == "production":
    csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins.split(",") if o.strip()]

    # -------------------------------------------------
    # 1) Credenciais / endpoint S3 (Supabase Storage S3 compat)
    # -------------------------------------------------
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")  # ex: https://<ref>.storage.supabase.co/storage/v1/s3
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "app-storage")

    if not AWS_S3_ENDPOINT_URL:
        raise RuntimeError("AWS_S3_ENDPOINT_URL não definido no ambiente de produção.")
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise RuntimeError("Credenciais AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY não definidas no ambiente de produção.")

    # Supabase S3-compat exige path-style
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "sa-east-1")

    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

    # -------------------------------------------------
    # 2) URL pública (SEM assinatura) para servir STATIC/MEDIA
    # -------------------------------------------------
    # Recomendado: defina SUPABASE_PROJECT_REF=agywyrlrgpcissozriwb
    SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")
    SUPABASE_PUBLIC_BASE = os.getenv("SUPABASE_PUBLIC_BASE")  # opcional: https://<ref>.supabase.co

    if SUPABASE_PUBLIC_BASE:
        public_host = SUPABASE_PUBLIC_BASE.rstrip("/")
    elif SUPABASE_PROJECT_REF:
        public_host = f"https://{SUPABASE_PROJECT_REF}.supabase.co"
    else:
        # Fallback (funciona se AWS_S3_ENDPOINT_URL for do formato padrão)
        parsed = urlparse(AWS_S3_ENDPOINT_URL)
        host = parsed.netloc  # <ref>.storage.supabase.co
        project_domain = host.replace(".storage.supabase.co", ".supabase.co")
        public_host = f"https://{project_domain}"

    PUBLIC_BASE = f"{public_host}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}"

    STATIC_URL = f"{PUBLIC_BASE}/static/"
    MEDIA_URL = f"{PUBLIC_BASE}/media/"

    # -------------------------------------------------
    # 3) Storages (Django 4.2+) - upload via S3 endpoint, URLs via custom_domain público
    # -------------------------------------------------
    # IMPORTANTE: custom_domain aqui deve ser sem o "https://"
    # para evitar duplicação em algumas versões do django-storages.
    PUBLIC_CUSTOM_DOMAIN = public_host.replace("https://", "").replace("http://", "")
    PUBLIC_CUSTOM_DOMAIN = f"{PUBLIC_CUSTOM_DOMAIN}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}"

    STORAGES = {
        "default": {  # MEDIA
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "addressing_style": AWS_S3_ADDRESSING_STYLE,
                "region_name": AWS_S3_REGION_NAME,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
                "location": "media",
                "default_acl": None,
                "file_overwrite": False,
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
                # Força URL pública (evita signed URLs)
                "custom_domain": PUBLIC_CUSTOM_DOMAIN,
            },
        },
        "staticfiles": {  # STATIC
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "addressing_style": AWS_S3_ADDRESSING_STYLE,
                "region_name": AWS_S3_REGION_NAME,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
                "location": "static",
                "default_acl": None,
                "file_overwrite": True,
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
                # Força URL pública (evita signed URLs)
                "custom_domain": PUBLIC_CUSTOM_DOMAIN,
            },
        },
    }

    # Em produção com S3, STATIC_ROOT/MEDIA_ROOT não são usados para servir,
    # mas alguns setups/collectstatic ainda usam como temporário local.
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

    print("✅ Modo PRODUÇÃO (Supabase Storage via S3)")
    print("ENVIRONMENT =", ENVIRONMENT)
    print("PUBLIC_BASE =", PUBLIC_BASE)
    print("STATIC_URL =", STATIC_URL)
else:
    # DEV local
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"

    STATICFILES_DIRS = [BASE_DIR / "static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

    print("✅ Modo DESENVOLVIMENTO")
    print("ENVIRONMENT =", ENVIRONMENT)
    print("STATIC_URL =", STATIC_URL)
# ==============================================================================
# 6. INTERNACIONALIZAÇÃO
# ==============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Debug prints finais
print(f"DEBUG Status: {DEBUG}")
print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
