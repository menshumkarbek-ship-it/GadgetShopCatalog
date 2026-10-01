import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _  # 🌐 Translation Engine
from dotenv import load_dotenv
import dj_database_url

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Convert DEBUG string from .env to boolean (default to False if not set)
DEBUG = os.getenv('DEBUG', 'False').strip().lower() == 'true'

# Require an explicit secret outside local development.
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-development-key'
    else:
        raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False.')

# Parse comma-separated string from .env into a list. Must be set in
# production (e.g. ALLOWED_HOSTS=your-app.onrender.com) — an empty list
# with DEBUG=False makes Django reject every request, so a forgotten env
# var fails closed instead of silently accepting any Host header.
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '').split(',') if host.strip()]

# 🔒 Django admin is mounted at a non-default path (instead of /admin/) to keep
# it off the beaten path for bots/scanners. Override via .env if needed; the
# trailing slash matters since it's used directly in a urls.py path().
ADMIN_URL = os.getenv('ADMIN_URL', 'system-console/').strip().strip('/') + '/'

# Google Search Console ownership token, rendered as a <meta> tag on every
# storefront page when set. Blank locally.
GOOGLE_SITE_VERIFICATION = os.getenv('GOOGLE_SITE_VERIFICATION', '').strip()

# The storefront has no customer accounts/login of its own (view-only catalog).
# Staff/managers authenticate through Django's admin login form, wherever
# ADMIN_URL happens to mount it, so @login_required views (the in-app product/
# category/contact management panel) send anonymous visitors there and back.
LOGIN_URL = 'admin:login'

# Send staff back to the storefront home after signing out, instead of
# rendering Django admin's own "logged out" confirmation page.
LOGOUT_REDIRECT_URL = 'shop:home'

INSTALLED_APPS = [
    'unfold',
    'django.contrib.admin',
    'storages',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'rest_framework',
    'drf_spectacular',
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'shop.middleware.SiteLanguageMiddleware',  # 🌐 Russian unless the visitor switches
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',  # 🌐 Language context
                'shop.context_processors.deployment',
                'shop.context_processors.is_admin',
                'shop.context_processors.contact_settings',
                'shop.context_processors.site_identity',
                'shop.context_processors.management_nav',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
# 🛰️ Enable the asynchronous server gateway interface routing matrix
ASGI_APPLICATION = 'config.asgi.application'

# Database configuration loaded dynamically from .env
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        # conn_health_checks: a pooled connection the database has since
        # dropped (a restart, an idle timeout on the managed plan) is replaced
        # instead of failing the next request with a 500.
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True, ssl_require=True)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': os.getenv('DB_NAME', 'mobile_shop_db'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==========================================
# 🌐 INTERNATIONALIZATION & MULTI-LANGUAGE
# ==========================================

# Every visitor gets Russian until they choose another language in the
# navbar switcher (see shop.middleware.SiteLanguageMiddleware, which ignores
# the browser's Accept-Language on purpose).
LANGUAGE_CODE = 'ru'

LANGUAGES = [
    ('en', _('English')),
    ('ru', _('Russian')),
    ('ky', _('Kyrgyz')),
]

# The switcher's choice is kept for a year. Django's default is a session
# cookie, so anyone who picked English or Kyrgyz would be back in Russian
# every time they reopened the browser.
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SAMESITE = 'Lax'

# Directory where translation files (.po / .mo) will be stored
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# The store's own clock. Timestamps are still stored in UTC (USE_TZ), but
# everything shown to staff — sale times, and which month a sale counts
# towards on the report — is Bishkek time, not six hours behind it.
TIME_ZONE = 'Asia/Bishkek'

USE_I18N = True

USE_TZ = True

# ==========================================
# 📁 MEDIA & STATIC FILES
# ==========================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Origins allowed to submit forms. Set explicitly if the site answers on more
# than its ALLOWED_HOSTS; otherwise derived from them, so a new domain only
# has to be added in one place (a leading-dot host becomes a wildcard).
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
] or [
    'https://' + ('*' + host if host.startswith('.') else host)
    for host in ALLOWED_HOSTS
    if host != '*'
]

# Base url to serve media files
MEDIA_URL = '/media/'

# Path where media files are physically stored on your computer (used only
# when R2 isn't configured — see STORAGES below).
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Cloudflare R2 (S3-compatible) for uploaded product/about images: a host's
# local disk doesn't survive redeploys, so this must live somewhere durable
# in production. Falls back to local disk automatically when the R2 env
# vars aren't set, so local dev needs no bucket.
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': R2_BUCKET_NAME,
            'access_key': os.getenv('R2_ACCESS_KEY_ID'),
            'secret_key': os.getenv('R2_SECRET_ACCESS_KEY'),
            'endpoint_url': os.getenv('R2_ENDPOINT_URL'),
            'custom_domain': os.getenv('R2_PUBLIC_DOMAIN') or None,
            'default_acl': None,
            # R2 only accepts SigV4; botocore defaults to SigV2-style
            # presigned URLs against a custom endpoint without this.
            'signature_version': 's3v4',
            # R2's raw API endpoint always requires a signed request, even
            # for a "public" bucket — actual public URLs only work through
            # a separate domain (R2.dev or a custom domain). Until
            # R2_PUBLIC_DOMAIN is set, fall back to presigned URLs so images
            # work out of the box; switch to plain URLs automatically once
            # a public domain is configured.
            'querystring_auth': not os.getenv('R2_PUBLIC_DOMAIN'),
        },
    } if R2_BUCKET_NAME else {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    # whitenoise.storage.CompressedManifestStaticFilesStorage adds
    # content-hashed filenames + gzip/brotli compression for static assets.
    # Django 6 only reads this via STORAGES (the legacy STATICFILES_STORAGE
    # setting is no longer honored, so setting only that name silently did
    # nothing).
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# The test suite runs with DEBUG off, where the manifest storage insists on a
# collectstatic having been run (and matching the current files). Tests only
# need the URLs, so they get the plain storage instead.
if sys.argv[1:2] == ['test']:
    STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}

# ==========================================
# 📑 DRF & API DOCUMENTATION SETTINGS
# ==========================================

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    # The catalog API is public and read-only, so the exposure to manage is
    # volume, not access: without paging, /api/products/ serialises the whole
    # table into one response, and without throttling a scraper can ask for
    # it in a loop.
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 24,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '120/min'},
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Store Catalog API',
    'DESCRIPTION': 'Read-only catalog of the products and categories on sale.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# In-process cache. Note this is per worker: the category list and the
# singleton settings cached against it are invalidated by signals, which only
# reach the worker that handled the write — so their timeouts are kept short
# (60s) rather than relying on invalidation alone. Swap in a shared backend
# here if the site ever runs enough workers for that to matter.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'shop-catalog',
    }
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# 🪵 LOGGING
# ==========================================

# Without this Django logs almost nothing once DEBUG=False, so anything that
# isn't a 500 is invisible on the host. Everything goes to stdout, which is
# what Render (and `docker compose logs`) collects.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO').upper(),
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Chatty at DEBUG (one line per query) and never wanted in production.
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ==========================================
# 🔒 HTTPS & PRODUCTION SECURITY SETTINGS
# ==========================================

if not DEBUG:
    # Force HTTP requests to redirect to HTTPS
    SECURE_SSL_REDIRECT = True

    # Send cookies over HTTPS only
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    LANGUAGE_COOKIE_SECURE = True

    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Inform Django it is behind a reverse proxy (Render / Vercel router)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
