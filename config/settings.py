from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-le9b$ui2r5s)ifc@4l8f2+q)ow@rm=ugi5g2po!nq@8t4d#4f8"

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
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("ARTICLE_AGENT_TASK_SOFT_TIME_LIMIT", "3300"))
ARTICLE_AGENT_MAX_RETRIES = int(os.getenv("ARTICLE_AGENT_MAX_RETRIES", "5"))
ARTICLE_AGENT_RETRY_BACKOFF_SECONDS = int(os.getenv("ARTICLE_AGENT_RETRY_BACKOFF_SECONDS", "60"))
ARTICLE_AGENT_MAX_WORD_COUNT = int(os.getenv("ARTICLE_AGENT_MAX_WORD_COUNT", "20000"))
ARTICLE_AGENT_MAX_HEADINGS = int(os.getenv("ARTICLE_AGENT_MAX_HEADINGS", "10"))
ARTICLE_AGENT_MAX_HEADING_LENGTH = int(os.getenv("ARTICLE_AGENT_MAX_HEADING_LENGTH", "255"))
ARTICLE_AGENT_MAX_KEYWORDS = int(os.getenv("ARTICLE_AGENT_MAX_KEYWORDS", "20"))
ARTICLE_AGENT_MAX_KEYWORD_LENGTH = int(os.getenv("ARTICLE_AGENT_MAX_KEYWORD_LENGTH", "120"))
ARTICLE_AGENT_MAX_SECTION_REVISIONS = int(os.getenv("ARTICLE_AGENT_MAX_SECTION_REVISIONS", "2"))
ARTICLE_AGENT_WORD_COUNT_TOLERANCE = float(os.getenv("ARTICLE_AGENT_WORD_COUNT_TOLERANCE", "0.25"))
ARTICLE_AGENT_LLM_TIMEOUT_SECONDS = int(os.getenv("ARTICLE_AGENT_LLM_TIMEOUT_SECONDS", "120"))


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


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
