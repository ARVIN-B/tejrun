import json
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import Agent, Chatbot
from apps.social_media_chatbot.infrastructure.persistence.models import InboundMessageEvent


class EvolutionWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.owner = get_user_model().objects.create_user(
            username="webhook-owner", password="pw"
        )
        cls.agent = Agent.objects.create(name="Webhook bots", slug="webhook-bots")
        cls.chatbot = Chatbot.objects.create(
            agent=cls.agent,
            owner=cls.owner,
            name="WA bot",
            social_media="whatsapp",
            evolution_instance_name="wa-1-abcd",
        )
        # Use a legacy plaintext row to exercise webhook validation without
        # requiring the not-yet-installed encrypted-field dependency.
        table = connection.ops.quote_name(Chatbot._meta.db_table)
        column = connection.ops.quote_name("social_webhook_secret")
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET {column}=%s WHERE id=%s",
                ["webhook-secret", cls.chatbot.pk],
            )

    def _url(self, secret="webhook-secret"):
        return reverse(
            "evolution_whatsapp_webhook",
            kwargs={"chatbot_id": self.chatbot.pk, "secret": secret},
        )

    def test_connection_update_event_updates_only_connection_state(self):
        response = self.client.post(
            self._url(),
            data=json.dumps({
                "event": "connection.update",
                "instance": self.chatbot.evolution_instance_name,
                "data": {"state": "open"},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.chatbot.refresh_from_db()
        self.assertEqual(self.chatbot.whatsapp_connection_state, "open")
        self.assertFalse(InboundMessageEvent.objects.exists())

    @patch("apps.social_media_chatbot.tasks.process_evolution_message.delay")
    def test_message_event_is_queued_once_for_duplicate_delivery(self, delay):
        payload = {
            "event": "messages.upsert",
            "instance": self.chatbot.evolution_instance_name,
            "data": {
                "key": {
                    "id": "message-1",
                    "remoteJid": "551234567890@s.whatsapp.net",
                    "fromMe": False,
                },
                "message": {"conversation": "hello"},
            },
        }
        first = self.client.post(
            self._url(), data=json.dumps(payload), content_type="application/json"
        )
        second = self.client.post(
            self._url(), data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(InboundMessageEvent.objects.count(), 1)
        delay.assert_called_once()

    def test_invalid_webhook_secret_is_rejected(self):
        response = self.client.post(
            self._url("wrong-secret"), data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
