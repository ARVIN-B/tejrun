import base64
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
import requests

from apps.social_media_chatbot.infrastructure.whatsapp import evolution


class EvolutionClientTests(SimpleTestCase):
    @override_settings(
        SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://127.0.0.1:8080",
        SOCIAL_MEDIA_CHATBOT_EVOLUTION_API_KEY="global-secret",
    )
    @patch("apps.social_media_chatbot.infrastructure.whatsapp.evolution.requests.Session")
    def test_create_instance_uses_global_key_and_separate_instance_token(self, session_factory):
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {
            "instance": {"status": "created"},
            "qrcode": {
                "base64": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
            },
        }
        session = session_factory.return_value
        session.__enter__.return_value = session
        session.request.return_value = response
        chatbot = SimpleNamespace(
            evolution_instance_name="wa-5-a1b2c3d4",
            platform_api_key="per-instance-token",
        )

        qr = evolution.create_instance(chatbot)

        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], ("POST", "http://127.0.0.1:8080/instance/create"))
        self.assertEqual(kwargs["headers"]["apikey"], "global-secret")
        self.assertEqual(kwargs["json"]["token"], "per-instance-token")
        self.assertEqual(kwargs["json"]["integration"], "WHATSAPP-BAILEYS")
        self.assertTrue(kwargs["json"]["qrcode"])
        self.assertEqual(
            qr,
            "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii"),
        )

    @override_settings(SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://127.0.0.1:8080")
    @patch("apps.social_media_chatbot.infrastructure.whatsapp.evolution.requests.Session")
    def test_message_send_uses_instance_token_and_plain_text_shape(self, session_factory):
        response = Mock(status_code=201, content=b"{}")
        response.json.return_value = {"key": {"id": "sent-1"}}
        session = session_factory.return_value
        session.__enter__.return_value = session
        session.request.return_value = response
        chatbot = SimpleNamespace(
            evolution_instance_name="wa-5-a1b2c3d4",
            platform_api_key="per-instance-token",
        )

        evolution.send_text(chatbot, "551234567890@s.whatsapp.net", "hello")

        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], (
            "POST",
            "http://127.0.0.1:8080/message/sendText/wa-5-a1b2c3d4",
        ))
        self.assertEqual(kwargs["headers"]["apikey"], "per-instance-token")
        self.assertEqual(kwargs["json"], {"number": "551234567890", "text": "hello"})

    @override_settings(SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://evolution.example.com:8080")
    def test_remote_plain_http_url_is_rejected(self):
        with self.assertRaises(evolution.EvolutionApiError):
            evolution._base_url()

    @override_settings(
        SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://evolution_api:8080"
    )
    def test_private_docker_service_url_is_allowed(self):
        self.assertEqual(
            evolution._base_url(), "http://evolution_api:8080"
        )

    @override_settings(
        SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://api.example.com:8080"
    )
    def test_public_plain_http_url_is_rejected(self):
        with self.assertRaises(evolution.EvolutionApiError):
            evolution._base_url()

    def test_rejects_untrusted_qr_data(self):
        self.assertIsNone(evolution._qr_data_url({"qrcode": {"base64": "<script>"}}))
        self.assertIsNone(evolution._qr_data_url({"qrcode": {"base64": "x" * 250_001}}))

    @override_settings(SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL="http://127.0.0.1:8080")
    @patch("apps.social_media_chatbot.infrastructure.whatsapp.evolution.requests.Session")
    def test_api_failure_is_sanitized(self, session_factory):
        session = session_factory.return_value
        session.__enter__.return_value = session
        session.request.side_effect = requests.ConnectionError("private-api-key-and-url")
        with self.assertRaises(evolution.EvolutionApiError) as raised:
            evolution._request("GET", "/instance/status", "do-not-leak")
        self.assertNotIn("private-api-key-and-url", str(raised.exception))
        self.assertNotIn("do-not-leak", str(raised.exception))
