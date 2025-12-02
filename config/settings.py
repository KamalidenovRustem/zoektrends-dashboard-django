"""
Django settings for ZoekTrends Dashboard project.
"""

import os
from pathlib import Path
import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'apps.authentication',
    'apps.dashboard',
    'apps.jobs',
    'apps.companies',
    'apps.analytics',
    'apps.configuration',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.authentication.middleware.SimpleAuthMiddleware',  # Custom auth
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}


# Password validation
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


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Brussels'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# CACHING CONFIGURATION
# =============================================================================
# Using local memory cache for development (no Redis required)
# Switch to Redis in production by uncommenting the Redis config below

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'zoektrends-cache',
        'TIMEOUT': 300,  # Default 5 minutes
    }
}

# For production with Redis, uncomment this:
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         },
#         'KEY_PREFIX': 'zoektrends',
#         'TIMEOUT': 300,
#     }
# }

# Cache TTL settings
CACHE_TTL_STATS = env.int('CACHE_TTL_STATS', default=300)
CACHE_TTL_JOBS = env.int('CACHE_TTL_JOBS', default=120)
CACHE_TTL_COMPANIES = env.int('CACHE_TTL_COMPANIES', default=180)


# =============================================================================
# SESSION CONFIGURATION
# =============================================================================
# Using database sessions for development (no Redis required)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE', default=86400)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
SESSION_COOKIE_HTTPONLY = env.bool('SESSION_COOKIE_HTTPONLY', default=True)
SESSION_COOKIE_SAMESITE = 'Lax'

# For production with Redis, use:
# SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
# SESSION_CACHE_ALIAS = 'default'


# =============================================================================
# GOOGLE CLOUD CONFIGURATION
# =============================================================================
GOOGLE_CLOUD = {
    'PROJECT_ID': env('GOOGLE_CLOUD_PROJECT_ID', default='agiliz-sales-tool'),
    'PROJECT_NUMBER': env('GOOGLE_CLOUD_PROJECT_NUMBER', default='904754592426'),
    'REGION': env('GOOGLE_CLOUD_REGION', default='europe-west1'),
    'CREDENTIALS_PATH': env('GOOGLE_APPLICATION_CREDENTIALS', default=''),
}

BIGQUERY = {
    'DATASET': env('BIGQUERY_DATASET', default='zoektrends_job_data'),
    'TABLE': env('BIGQUERY_TABLE', default='job_postings'),
    'COMPANIES_TABLE': env('BIGQUERY_COMPANIES_TABLE', default='companies'),
    'SKILLS_REGISTRY_TABLE': env('BIGQUERY_SKILLS_REGISTRY_TABLE', default='skills_registry'),
}

CLOUD_RUN = {
    'JOB_NAME': env('CLOUD_RUN_JOB_NAME', default='zoektrends-exhaustive'),
    'TIMEOUT': env.int('CLOUD_RUN_TIMEOUT', default=1800),
}


# =============================================================================
# LOOKER CONFIGURATION
# =============================================================================
LOOKER = {
    'HOST': env('LOOKER_HOST', default=''),
    'EMBED_SECRET': env('LOOKER_EMBED_SECRET', default=''),
    'EMBED_USER': env('LOOKER_EMBED_USER', default='embed_user@zoektrends.com'),
    'DEFAULT_DASHBOARD_ID': env('LOOKER_DEFAULT_DASHBOARD_ID', default=''),
    'CLIENT_ID': env('LOOKER_CLIENT_ID', default=''),
    'CLIENT_SECRET': env('LOOKER_CLIENT_SECRET', default=''),
}


# =============================================================================
# DASHBOARD CONFIGURATION
# =============================================================================
DASHBOARD = {
    'RESULTS_LIMIT': env.int('DASHBOARD_RESULTS_LIMIT', default=500),
    'MAX_RESULTS_LIMIT': env.int('DASHBOARD_MAX_RESULTS_LIMIT', default=1000),
}


# =============================================================================
# AI SERVICES CONFIGURATION
# =============================================================================
# OpenAI API
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')

# AI Provider selection: 'gemini' or 'openai'
AI_CONTACT_PROVIDER = env('AI_CONTACT_PROVIDER', default='gemini')

# SerpAPI for Google Search
SERPAPI_KEY = env('SERPAPI_KEY', default='')


# =============================================================================
# AUTHENTICATION CONFIGURATION
# =============================================================================
# Authentication - Simple username/password (Laravel style)
DASHBOARD_USERNAME = env('DASHBOARD_USERNAME', default='admin')
DASHBOARD_PASSWORD = env('DASHBOARD_PASSWORD', default='admin')


# =============================================================================
# CELERY CONFIGURATION
# =============================================================================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE


# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


# =============================================================================
# CORS CONFIGURATION
# =============================================================================
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost',
    'http://127.0.0.1',
])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all origins in development


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': env('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': env('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)


# =============================================================================
# SECURITY SETTINGS
# =============================================================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
