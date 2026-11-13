"""Fields used by the persisted chatbot configuration model."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


_PREFIX = "enc:v1:"


def _fernet():
    key = getattr(settings, "SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "Set SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY before using chatbot credentials."
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("ascii"))
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Install the already-declared cryptography dependency before using chatbot credentials."
        ) from exc
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured(
            "SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


def encrypt_secret(value: str) -> str:
    if not value or value.startswith(_PREFIX):
        return value
    return _PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            "Could not decrypt chatbot credentials; verify the configured encryption key."
        ) from exc


class EncryptedTextField(models.TextField):
    """Encrypt chatbot credentials before database writes and decrypt reads."""

    def from_db_value(self, value, expression, connection):
        return decrypt_secret(value) if value is not None else value

    def to_python(self, value):
        return decrypt_secret(value) if value is not None else value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_secret(value) if value is not None else value
