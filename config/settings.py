from pathlib import Path
import os
import sys
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# A deployment must explicitly provide a strong secret. Tests receive an
# isolated ephemeral key so they never weaken production configuration.
_provided_secret = os.getenv("DJANGO_SECRET_KEY", "")
if not _provided_secret:
    if "test" in sys.argv:
        SECRET_KEY = "test-only-article-agent-secret-key-not-for-production-123456789"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong secret outside tests."
        )
else:
    SECRET_KEY = _provided_secret

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() == "true"


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.agents",
    "apps.social_media_chatbot",
    "apps.dashboard",
    "apps.article_agent",
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Article generation is deliberately delegated to Celery. Redis is only a
# broker/result backend; PostgreSQL and file storage remain the durable source.
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.article_agent.tasks.generate_article_task": {"queue": "article_generation"},
}
CELERY_TASK_TIME_LIMIT = int(os.getenv("ARTICLE_AGENT_TASK_TIME_LIMIT", "3600"))
CELERY_TASK_SOFT_TIME_LIMIT = int(
    os.getenv("ARTICLE_AGENT_TASK_SOFT_TIME_LIMIT", "3300")
)
ARTICLE_AGENT_MAX_RETRIES = int(os.getenv("ARTICLE_AGENT_MAX_RETRIES", "5"))
ARTICLE_AGENT_RETRY_BACKOFF_SECONDS = int(
    os.getenv("ARTICLE_AGENT_RETRY_BACKOFF_SECONDS", "60")
)
ARTICLE_AGENT_MAX_WORD_COUNT = int(os.getenv("ARTICLE_AGENT_MAX_WORD_COUNT", "20000"))
ARTICLE_AGENT_MAX_HEADINGS = int(os.getenv("ARTICLE_AGENT_MAX_HEADINGS", "10"))
ARTICLE_AGENT_MAX_HEADING_LENGTH = int(
    os.getenv("ARTICLE_AGENT_MAX_HEADING_LENGTH", "255")
)
ARTICLE_AGENT_MAX_KEYWORDS = int(os.getenv("ARTICLE_AGENT_MAX_KEYWORDS", "20"))
ARTICLE_AGENT_MAX_KEYWORD_LENGTH = int(
    os.getenv("ARTICLE_AGENT_MAX_KEYWORD_LENGTH", "120")
)
ARTICLE_AGENT_MAX_SECTION_REVISIONS = int(
    os.getenv("ARTICLE_AGENT_MAX_SECTION_REVISIONS", "2")
)
ARTICLE_AGENT_WORD_COUNT_TOLERANCE = float(
    os.getenv("ARTICLE_AGENT_WORD_COUNT_TOLERANCE", "0.25")
)
ARTICLE_AGENT_LLM_TIMEOUT_SECONDS = int(
    os.getenv("ARTICLE_AGENT_LLM_TIMEOUT_SECONDS", "120")
)
ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS = int(
    os.getenv("ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS", "8192")
)
ARTICLE_AGENT_MAX_BUDGET_REPAIRS = int(
    os.getenv("ARTICLE_AGENT_MAX_BUDGET_REPAIRS", "3")
)
if ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS < 256:
    raise ImproperlyConfigured(
        "ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS must be at least 256."
    )
if ARTICLE_AGENT_MAX_BUDGET_REPAIRS < 0:
    raise ImproperlyConfigured("ARTICLE_AGENT_MAX_BUDGET_REPAIRS cannot be negative.")
ARTICLE_AGENT_RESEARCH_MODE = os.getenv(
    "ARTICLE_AGENT_RESEARCH_MODE", "disabled"
).lower()
ARTICLE_AGENT_RESEARCH_TIMEOUT_SECONDS = int(
    os.getenv("ARTICLE_AGENT_RESEARCH_TIMEOUT_SECONDS", "20")
)
ARTICLE_AGENT_GROQ_CONCURRENCY = int(os.getenv("ARTICLE_AGENT_GROQ_CONCURRENCY", "4"))
ARTICLE_AGENT_GROQ_REQUESTS_PER_MINUTE = int(
    os.getenv("ARTICLE_AGENT_GROQ_REQUESTS_PER_MINUTE", "30")
)
ARTICLE_AGENT_GROQ_TOKENS_PER_MINUTE = int(
    os.getenv("ARTICLE_AGENT_GROQ_TOKENS_PER_MINUTE", "30000")
)


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.invalid")


if DEBUG:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "195.248.240.152",
    ]

    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://195.248.240.152:3000",
    ]

    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://195.248.240.152:3000",
    ]
else:
    ALLOWED_HOSTS = [
        "195.248.240.152",
        # "example.com",
        # "www.example.com",
    ]

    CORS_ALLOWED_ORIGINS = [
        # "https://example.com",
        # "https://www.example.com",
    ]

    CSRF_TRUSTED_ORIGINS = [
        # "https://example.com",
        # "https://www.example.com",
    ]

LOGIN_URL = "/login/"

if not DEBUG and "test" not in sys.argv:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
