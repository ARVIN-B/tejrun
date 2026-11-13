from django.urls import path
from apps.social_media_chatbot.presentation.web import views as chatbot_views

# from .views import dashboard_view, login_view
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("", views.dashboard_view, name="dashboard"),
    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),
    
    path(
        "social-media-agent/chatbots/",
        chatbot_views.chatbot_list,
        name="social_media_chatbots",
    ),
    path(
        "social-media-agent/chatbots/new/",
        chatbot_views.chatbot_create,
        name="social_media_chatbot_create",
    ),
    path(
        "social-media-agent/chatbots/<int:chatbot_id>/edit/",
        chatbot_views.chatbot_edit,
        name="social_media_chatbot_edit",
    ),
    path(
        "social-media-agent/chatbots/<int:chatbot_id>/toggle/",
        chatbot_views.chatbot_toggle,
        name="social_media_chatbot_toggle",
    ),
    path(
        "social-media-agent/chatbots/<int:chatbot_id>/whatsapp-connect/",
        chatbot_views.chatbot_whatsapp_connect,
        name="social_media_chatbot_whatsapp_connect",
    ),
    path(
        "social-media-agent/chatbots/<int:chatbot_id>/delete/",
        chatbot_views.chatbot_delete,
        name="social_media_chatbot_delete",
    ),
]
