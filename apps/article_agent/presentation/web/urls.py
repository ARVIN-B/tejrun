from django.urls import path

from . import views


urlpatterns = [
    path("", views.create_article_view, name="article_agent"),
    path("create/", views.create_article_job, name="article_job_create"),
    path("jobs/<int:job_id>/", views.job_status, name="article_job_status"),
    path("jobs/<int:job_id>/cancel/", views.cancel_job, name="article_job_cancel"),
    path("jobs/<int:job_id>/retry/", views.retry_job, name="article_job_retry"),
    path("jobs/<int:job_id>/download/", views.download_job, name="article_job_download"),
]
