from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.agents.models import Agent, Chatbot


class ChatbotTenantAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="tenant-owner", password="pw")
        cls.other_owner = User.objects.create_user(username="other-owner", password="pw")
        cls.agent = Agent.objects.create(name="Tenant bots", slug="tenant-bots")
        cls.own_bot = Chatbot.objects.create(
            agent=cls.agent,
            owner=cls.owner,
            name="My Telegram bot",
            social_media="telegram",
        )
        cls.other_bot = Chatbot.objects.create(
            agent=cls.agent,
            owner=cls.other_owner,
            name="Other WhatsApp bot",
            social_media="whatsapp",
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def test_bot_list_and_dashboard_menu_are_owner_scoped(self):
        response = self.client.get(reverse("social_media_chatbots"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.own_bot.name)
        self.assertNotContains(response, self.other_bot.name)

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.other_bot.name)

    def test_other_tenant_cannot_view_edit_toggle_or_delete_bot(self):
        self.assertEqual(
            self.client.get(
                reverse("social_media_chatbot_edit", args=[self.other_bot.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("social_media_chatbot_toggle", args=[self.other_bot.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("social_media_chatbot_delete", args=[self.other_bot.pk])
            ).status_code,
            404,
        )
        self.assertTrue(Chatbot.objects.filter(pk=self.other_bot.pk).exists())

    def test_other_tenant_cannot_request_whatsapp_qr(self):
        response = self.client.get(
            reverse("social_media_chatbot_whatsapp_connect", args=[self.other_bot.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_chat_api_does_not_resolve_another_tenants_bot(self):
        response = self.client.post(
            "/api/social-media-chatbot/chat/",
            {
                "bot_id": self.other_bot.pk,
                "external_id": "external-user",
                "message": "hello",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_chatbot_toggle_rejects_post_without_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.post(
            reverse("social_media_chatbot_toggle", args=[self.own_bot.pk])
        )
        self.assertEqual(response.status_code, 403)
