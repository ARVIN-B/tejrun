from django.urls import path

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
        views.social_media_chatbots_view,
        name="social_media_chatbots",
    ),
]
