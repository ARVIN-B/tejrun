from django.urls import path

from .views import ChatView, evolution_whatsapp_webhook


urlpatterns = [
    path("chat/", ChatView.as_view(), name="social-media-chat"),
    path(
        "evolution/<int:chatbot_id>/<str:secret>/",
        evolution_whatsapp_webhook,
        name="evolution_whatsapp_webhook",
    ),
]
