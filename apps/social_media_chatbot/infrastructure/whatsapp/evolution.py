"""Server-side client for the shared Evolution API v2 service."""

import base64
import ipaddress
from io import BytesIO
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.urls import reverse


class EvolutionApiError(Exception):
    """A sanitized Evolution API communication or configuration failure."""


def _base_url():
    value = settings.SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL
    if not value:
        raise EvolutionApiError("Evolution API base URL is not configured.")
    parsed = urlparse(value)
    hostname = parsed.hostname
    if not hostname or parsed.username or parsed.password:
        raise EvolutionApiError("Evolution API base URL is invalid.")
    is_loopback = hostname in {"localhost", "127.0.0.1", "::1"}
    is_private_ip = False
    try:
        address = ipaddress.ip_address(hostname)
        is_private_ip = address.is_private or address.is_loopback or address.is_link_local
    except ValueError:
        # Docker service names (for example evolution_api) and explicitly
        # private DNS zones are valid only for operator-controlled config.
        is_private_ip = "." not in hostname or hostname.endswith((".internal", ".local"))
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and (is_loopback or is_private_ip)
    ):
        raise EvolutionApiError("Evolution API must use HTTPS outside local development.")
    return value.rstrip("/")


def _global_api_key():
    value = settings.SOCIAL_MEDIA_CHATBOT_EVOLUTION_API_KEY
    if not value:
        raise EvolutionApiError("Evolution API server credential is not configured.")
    return value


def _public_base_url():
    value = settings.SOCIAL_MEDIA_CHATBOT_PUBLIC_BASE_URL
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise EvolutionApiError("Public callback URL must use HTTPS.")
    return value.rstrip("/")


def webhook_url(chatbot):
    return _public_base_url() + reverse(
        "evolution_whatsapp_webhook",
        kwargs={"chatbot_id": chatbot.pk, "secret": chatbot.social_webhook_secret},
    )


def _instance_path(chatbot, suffix=""):
    return f"/{suffix}{quote(chatbot.evolution_instance_name, safe='')}"


def create_instance(chatbot):
    """Create a Baileys instance with a unique token and return any initial QR."""
    result = _request(
        "POST",
        "/instance/create",
        _global_api_key(),
        {
            "instanceName": chatbot.evolution_instance_name,
            "token": chatbot.platform_api_key,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        },
    )
    return _qr_data_url(result)


def connect_instance(chatbot):
    """Ensure an instance exists, install its webhook and retrieve a fresh QR."""
    state_data = _request(
        "GET",
        _instance_path(chatbot, "instance/connectionState/"),
        chatbot.platform_api_key,
        allow_not_found=True,
    )
    qr = None
    if state_data is None:
        qr = create_instance(chatbot)

    configure_instance_webhook(chatbot)
    state_data = _request(
        "GET",
        _instance_path(chatbot, "instance/connectionState/"),
        chatbot.platform_api_key,
    )
    state = ((state_data.get("instance") or {}).get("state") or "connecting").lower()
    if state == "open":
        qr = None
    if state != "open" and not qr:
        qr_result = _request(
            "GET",
            _instance_path(chatbot, "instance/connect/"),
            chatbot.platform_api_key,
        )
        qr = _qr_data_url(qr_result)
    return state, qr


def connection_state(chatbot):
    result = _request(
        "GET",
        _instance_path(chatbot, "instance/connectionState/"),
        chatbot.platform_api_key,
        allow_not_found=True,
    )
    if result is None:
        return "not_configured"
    return (((result.get("instance") or {}).get("state")) or "connecting").lower()


def configure_instance_webhook(chatbot):
    _request(
        "POST",
        _instance_path(chatbot, "webhook/set/"),
        chatbot.platform_api_key,
        {
            "enabled": True,
            "url": webhook_url(chatbot),
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
        },
    )


def disable_instance_webhook(chatbot):
    _request(
        "POST",
        _instance_path(chatbot, "webhook/set/"),
        chatbot.platform_api_key,
        {
            "enabled": False,
            "url": webhook_url(chatbot),
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
        },
    )


def delete_instance(chatbot):
    _request(
        "DELETE",
        _instance_path(chatbot, "instance/delete/"),
        _global_api_key(),
        allow_not_found=True,
    )


def send_text(chatbot, number: str, text: str):
    recipient = number.split("@", 1)[0]
    _request(
        "POST",
        _instance_path(chatbot, "message/sendText/"),
        chatbot.platform_api_key,
        {"number": recipient, "text": text},
    )


def _qr_data_url(payload):
    if not isinstance(payload, dict):
        return None
    qr = payload.get("qrcode") or payload.get("qrCode") or payload
    if not isinstance(qr, dict):
        return None
    value = qr.get("base64") or qr.get("qrcode")
    if not value:
        value = qr.get("code")
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("data:image/"):
        prefix, separator, image_data = value.partition(",")
        if (
            not separator
            or prefix != "data:image/png;base64"
            or len(value) > 250_000
            or not _is_base64_png(image_data)
        ):
            return None
        return value
    if len(value) > 250_000 or any(
        char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-@"
        for char in value
    ):
        return None
    if qr.get("base64") or qr.get("qrcode"):
        if not _is_base64_png(value):
            return None
        return f"data:image/png;base64,{value}"

    # Evolution v2's connect endpoint can return the QR payload string instead
    # of an image. Render it locally so pairing data never leaves this server.
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage

        image = qrcode.make(value, image_factory=SvgPathImage, border=4, box_size=8)
        output = BytesIO()
        image.save(output)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    except ImportError as exc:
        raise EvolutionApiError(
            "The app-specific QR rendering dependency is not installed."
        ) from None


def _is_base64_png(value):
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    return decoded.startswith(b"\x89PNG\r\n\x1a\n")


def _request(method, path, api_key, payload=None, *, allow_not_found=False):
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(
                method,
                _base_url() + path,
                headers={"apikey": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=(3, 15),
            )
            if allow_not_found and response.status_code == 404:
                return None
            response.raise_for_status()
            if not response.content:
                return {}
            result = response.json()
            return result if isinstance(result, dict) else {}
    except (requests.RequestException, ValueError, EvolutionApiError):
        # Exception context can contain URLs or headers. Never chain it into
        # app logs or expose Evolution's response body to a dashboard user.
        raise EvolutionApiError("Evolution API request failed.") from None
