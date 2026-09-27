from django.urls import path

from .views import ChatView


urlpatterns = [
    path("chat/", ChatView.as_view(), name="social-media-chat"),
]