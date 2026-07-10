"""
Django settings for vvp_app_server project.
"""

import os
import sys
from pathlib import Path

import environ  # type: ignore[reportMissingTypeStubs]

env = environ.Env(DEBUG=(str, "disabled"))

environ.Env.read_env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG") == "enabled"

# Settings for handling proxy and CDN
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Session and cookie settings
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Disable HTTPS redirect in development
if DEBUG:
    SECURE_SSL_REDIRECT = False
else:
    SECURE_SSL_REDIRECT = True

# Security hardening for production
if not DEBUG:
    # HTTP Strict Transport Security
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Other secure headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "no-referrer-when-downgrade"

    # Enforce cookies to HTTPOnly
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True

    # Ensure SSL redirect
    from django.core.exceptions import ImproperlyConfigured

    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured("SECURE_SSL_REDIRECT must be True in production")

ALLOWED_HOSTS = [
    "mimikamaserver.azurewebsites.net",
    "pruefpunkt.org",
    "staging.volksverpetzer-app.de",
    "volksverpetzer-app.de",
    "127.0.0.1",
    "localhost",
    "20.105.232.42",
    "169.254.131.2",
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "notifications",
    "factApi",
    "reportFake",
    "contact",
    "payment",
    "proxycache",
    "info",
    "django_q",
    "django_bootstrap5",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "vvp_app_server.middleware.EdgeCacheControlMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_ratelimit.middleware.RatelimitMiddleware",
]

CORS_ALLOWED_ORIGINS = [
    "https://www.volksverpetzer.de",
    "https://volksverpetzer.de",
    "https://volksverpetzer-app.de",
    "https://staging.volksverpetzer-app.de",
]

if DEBUG:
    CORS_ALLOWED_ORIGINS.append("http://localhost:8899")

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://([a-zA-Z0-9-]+\.)?volksverpetzer\.de$",
    r"^https://([a-zA-Z0-9-]+\.)?volksverpetzer-app\.de$",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://www.volksverpetzer.de",
    "https://volksverpetzer.de",
    "https://volksverpetzer-app.de",
    "https://staging.volksverpetzer-app.de",
]
# 127.0.0.1 and localhost are added to CSRF_TRUSTED_ORIGINS for development
if DEBUG:
    CSRF_TRUSTED_ORIGINS.append("http://127.0.0.1:8000")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:8000")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:8899")

ROOT_URLCONF = "vvp_app_server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "vvp_app_server.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
if "test" in sys.argv:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DB = env.db("DATABASE_URL", default="sqlite:///db.sqlite3")  # type: ignore[reportUnknownParameterType]
    db_options: dict[str, str] = {}
    if DB.get("ENGINE", "").endswith("postgresql"):
        db_options["sslmode"] = os.getenv("DB_SSLMODE") or "require"
        sslrootcert = os.getenv("DB_SSLROOTCERT")
        if sslrootcert:
            db_options["sslrootcert"] = sslrootcert

    DATABASES = {
        "default": {
            **DB,
            "OPTIONS": {**(DB.get("OPTIONS") or {}), **db_options},
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "vvp_locmem",
        "TIMEOUT": 60 * 60 * 24,  # 1 day
    },
    "persistent": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
        "TIMEOUT": 60 * 60 * 24 * 7,  # 7 days
    },
}

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
STATIC_ROOT = BASE_DIR / "static"
STATIC_URL = "/static/"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django-ratelimit settings
RATELIMIT_ENABLE = env("RATELIMIT_ENABLE", default="true") == "true"
RATELIMIT_VIEW = "reportFake.views.ratelimit_view"
# Use the shared DatabaseCache so rate-limit counters are consistent across
# all Gunicorn workers and processes (LocMemCache is per-process only).
# DatabaseCache is shared across Gunicorn workers (unlike LocMemCache which is
# per-process). It is not atomically consistent under high concurrency — Redis
# would be strictly correct — but it is a significant improvement over the
# per-process default. Requires `manage.py createcachetable` to be run once.
RATELIMIT_USE_CACHE = "persistent"

# Use custom test runner to show coverage report
TEST_RUNNER = "vvp_app_server.test_runner.CoverageTestRunner"

Q_CLUSTER = {
    "name": "DjangORM",
    "workers": 1,
    "recycle": 200,
    "max_attempts": 1,
    "timeout": 1800,
    "retry": 2400,
    "catch_up": False,
    "bulk": 10,
    "orm": "default",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"},  # noqa: E501
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "notifications": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
