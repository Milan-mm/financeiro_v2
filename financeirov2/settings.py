from pathlib import Path
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import dj_database_url # Facilita a vida com o Supabase

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 1. CARREGAMENTO DE AMBIENTE (Seu snippet adaptado)
# ==============================================================================

# Qual ambiente estou rodando? (development ou production)
# No Railway, defina a variável DJANGO_ENV = production nas configurações
ENVIRONMENT = os.getenv("DJANGO_ENV", "production")

# Escolhe o arquivo .env com base no ambiente
if ENVIRONMENT == "production":
    env_file = ".env.production"
else:
    env_file = ".env.development"

env_path = BASE_DIR / env_file

if env_path.exists():
    # AQUI ESTÁ A CORREÇÃO DO ERRO 0xe3 (Unicode): encoding="utf-8"
    load_dotenv(env_path, encoding="utf-8")
    print(f"✓ Arquivo .env carregado: {env_file}")
else:
    print(f"⚠️ Arquivo .env não encontrado: {env_file}. Usando variáveis de ambiente do sistema.")

print(f"Ambiente atual: {ENVIRONMENT}")

# ==============================================================================
# 2. CONFIGURAÇÕES GERAIS
# ==============================================================================

# DEBUG: Em produção deve ser sempre False, mas lemos do env por segurança
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# SECRET_KEY: Obrigatória
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-chave-padrao-dev")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,.railway.app").split(",")

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
            conn_max_age=600,
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

# ==============================================================================
# 5. ARQUIVOS ESTÁTICOS (CSS/JS)
# ==============================================================================

if ENVIRONMENT == "production":
    # Credenciais / endpoint
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

    # Monta domínio público para servir arquivos via endpoint público do Supabase
    # Endpoint S3: https://<ref>.storage.supabase.co/storage/v1/s3
    # Público:      https://<ref>.supabase.co/storage/v1/object/public/<bucket>
    parsed = urlparse(AWS_S3_ENDPOINT_URL)
    host = parsed.netloc  # <ref>.storage.supabase.co
    project_domain = host.replace(".storage.supabase.co", ".supabase.co")
    PUBLIC_BASE = f"https://{project_domain}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}"

    # Storages (Django 4.2+)
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
            },
        },
    }

    STATIC_URL = f"{PUBLIC_BASE}/static/"
    MEDIA_URL = f"{PUBLIC_BASE}/media/"

    # Em produção com S3, STATIC_ROOT/MEDIA_ROOT não são usados para servir,
    # mas o collectstatic ainda cria temporários localmente dependendo do setup.
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

    print("✅ Modo PRODUÇÃO (S3)")
    print("ENVIRONMENT =", ENVIRONMENT)
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