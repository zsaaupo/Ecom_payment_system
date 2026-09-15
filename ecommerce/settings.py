"""
Django settings for the E-commerce Ordering & Payment System.

Environment configuration is read from a .env file at the project root
(see .env.example). This keeps secrets (API keys, webhook secrets) out
of source control, per the assessment's non-functional requirement:
"Secure storage of API keys."
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Minimal .env loader (no third-party dependency required)
# ---------------------------------------------------------------------------
def load_env_file(path):
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env_file(BASE_DIR / ".env")


def env(key, default=None):
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production-6f92a1c3")

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",") if h.strip()
]

# ngrok / external origins configuration driven by .env
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",

    "users",
    "products",
    "orders",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ecommerce.urls"

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

WSGI_APPLICATION = "ecommerce.wsgi.application"
ASGI_APPLICATION = "ecommerce.asgi.application"


# ---------------------------------------------------------------------------
# Database - SQLite (per assessment: "Use SQLite for now")
# ---------------------------------------------------------------------------
# DJANGO_DB_DIR lets Docker mount a persistent volume for the SQLite file
# (defaults to the project root for plain `python manage.py runserver` use).
DB_DIR = Path(env("DJANGO_DB_DIR", str(BASE_DIR)))
DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_DIR / "db.sqlite3",
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 60},
    }
}


# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]




# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# CORS (frontend on Vercel talking to backend over ngrok)
# ---------------------------------------------------------------------------
from corsheaders.defaults import default_headers

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOWED_ORIGINS = [o.strip() for o in env('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = list(default_headers) + [
    "ngrok-skip-browser-warning",
]


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}


# ---------------------------------------------------------------------------
# Caching - used to cache the category tree (DFS + Caching requirement).
# Defaults to Django's local-memory cache so the project runs out of the box
# with zero extra services. Set REDIS_URL to switch to Redis/memcached in
# production without changing any application code (see products/services.py).
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", "")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ecommerce-locmem-cache",
        }
    }

CATEGORY_TREE_CACHE_KEY = "products:category_tree_v1"
CATEGORY_TREE_CACHE_TTL = int(env("CATEGORY_TREE_CACHE_TTL", "3600"))


# ---------------------------------------------------------------------------
# Payment providers - Stripe & bKash (Strategy pattern, see payments/strategies.py)
# ---------------------------------------------------------------------------
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")

# Catalog prices use one currency. Existing catalog prices were displayed in USD.
STORE_CURRENCY = env("STORE_CURRENCY", "USD").upper()
if STORE_CURRENCY not in ("USD", "BDT"):
    raise ValueError("STORE_CURRENCY must be USD or BDT.")

BKASH_BASE_URL = env("BKASH_BASE_URL", "https://tokenized.sandbox.bka.sh/v1.2.0-beta")
BKASH_APP_KEY = env("BKASH_APP_KEY", "")
BKASH_APP_SECRET = env("BKASH_APP_SECRET", "")
BKASH_USERNAME = env("BKASH_USERNAME", "")
BKASH_PASSWORD = env("BKASH_PASSWORD", "")
BKASH_CALLBACK_URL = env("BKASH_CALLBACK_URL", "http://localhost:8000/api/payments/webhooks/bkash/")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:8080").rstrip("/")


# ---------------------------------------------------------------------------
# Logging - "Logging & error handling" non-functional requirement
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "payments": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        "orders": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        "products": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
    },
}
