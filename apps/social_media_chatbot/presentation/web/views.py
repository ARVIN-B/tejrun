from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
import logging
import uuid
import secrets

from apps.agents.models import Agent, Chatbot

from .forms import ChatbotForm
from apps.social_media_chatbot.infrastructure.whatsapp.evolution import (
    EvolutionApiError,
    configure_instance_webhook,
    connect_instance,
    connection_state,
    delete_instance,
    disable_instance_webhook,
)


logger = logging.getLogger(__name__)


def _sync_whatsapp_webhook(chatbot, *, enabled):
    if chatbot.social_media != "whatsapp":
        return True
    try:
        if enabled:
            configure_instance_webhook(chatbot)
        else:
            disable_instance_webhook(chatbot)
        chatbot.evolution_webhook_configured = enabled
        chatbot.save(update_fields=["evolution_webhook_configured", "updated_at"])
        return True
    except EvolutionApiError:
        logger.warning("Evolution webhook configuration failed for chatbot id=%s", chatbot.pk)
        chatbot.evolution_webhook_configured = False
        chatbot.save(update_fields=["evolution_webhook_configured", "updated_at"])
        return False


def _management_agent(owner):
    agent, _ = Agent.objects.get_or_create(
        slug=f"social-media-chatbots-{owner.pk}",
        defaults={
            "name": "Social Media Chatbots",
            "description": "Bots managed from the Social Media Chatbot dashboard.",
            "is_active": True,
        },
    )
    return agent


@login_required
def chatbot_list(request):
    chatbots = Chatbot.objects.filter(owner=request.user).only(
        "id",
        "name",
        "social_media",
        "is_active",
        "evolution_webhook_configured",
        "system_prompt",
        "brand_name",
        "created_at",
    ).order_by("-created_at")
    return render(
        request,
        "dashboard/social_media_chatbots.html",
        {
            "chatbots": chatbots,
            "active_count": chatbots.filter(is_active=True).count(),
            "editing": None,
        },
    )


@login_required
def chatbot_create(request):
    form = ChatbotForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        chatbot = form.save(commit=False)
        chatbot.agent = _management_agent(request.user)
        chatbot.owner = request.user
        chatbot.is_active = True
        if chatbot.social_media == "whatsapp":
            chatbot.evolution_instance_name = f"wa-{request.user.pk}-{uuid.uuid4().hex[:16]}"
            chatbot.platform_api_key = str(uuid.uuid4())
            chatbot.social_webhook_secret = secrets.token_urlsafe(32)
            chatbot.whatsapp_connection_state = "creating"
        chatbot.save()
        if chatbot.social_media == "whatsapp":
            qr_data_url = None
            try:
                chatbot.whatsapp_connection_state, qr_data_url = connect_instance(chatbot)
                chatbot.evolution_webhook_configured = True
                chatbot.save(update_fields=[
                    "whatsapp_connection_state",
                    "evolution_webhook_configured",
                    "updated_at",
                ])
            except EvolutionApiError:
                chatbot.whatsapp_connection_state = "error"
                chatbot.evolution_webhook_configured = False
                chatbot.save(update_fields=[
                    "whatsapp_connection_state",
                    "evolution_webhook_configured",
                    "updated_at",
                ])
                messages.warning(request, "بات ذخیره شد، اما اتصال Evolution کامل نشد. از گزینه اتصال مجدد تلاش کن.")
            response = render(
                request,
                "dashboard/chatbot_whatsapp_connect.html",
                {"chatbot": chatbot, "qr_data_url": qr_data_url},
            )
            response["Cache-Control"] = "no-store, private"
            response["Referrer-Policy"] = "no-referrer"
            return response
        messages.success(request, "بات با موفقیت ساخته و فعال شد.")
        return redirect("social_media_chatbots")
    return render(request, "dashboard/chatbot_form.html", {"form": form, "is_create": True})


@login_required
def chatbot_edit(request, chatbot_id):
    chatbot = get_object_or_404(Chatbot, pk=chatbot_id, owner=request.user)
    form = ChatbotForm(request.POST or None, request.FILES or None, instance=chatbot)
    if request.method == "POST" and form.is_valid():
        chatbot = form.save()
        webhook_ok = _sync_whatsapp_webhook(chatbot, enabled=chatbot.is_active)
        if webhook_ok:
            messages.success(request, "تنظیمات بات ذخیره شد.")
        else:
            messages.warning(request, "تنظیمات ذخیره شد، اما webhook در Evolution API هماهنگ نشد.")
        return redirect("social_media_chatbots")
    return render(
        request,
        "dashboard/chatbot_form.html",
        {"form": form, "is_create": False, "chatbot": chatbot},
    )


@login_required
@require_POST
def chatbot_toggle(request, chatbot_id):
    chatbot = get_object_or_404(Chatbot, pk=chatbot_id, owner=request.user)
    chatbot.is_active = not chatbot.is_active
    chatbot.save(update_fields=["is_active", "updated_at"])
    webhook_ok = _sync_whatsapp_webhook(chatbot, enabled=chatbot.is_active)
    status_text = "فعال" if chatbot.is_active else "غیرفعال"
    if webhook_ok:
        messages.success(request, f"بات {status_text} شد.")
    else:
        messages.warning(request, f"بات {status_text} شد، اما webhook در Evolution API هماهنگ نشد.")
    return redirect("social_media_chatbots")


@login_required
@require_POST
def chatbot_delete(request, chatbot_id):
    chatbot = get_object_or_404(Chatbot, pk=chatbot_id, owner=request.user)
    if chatbot.social_media == "whatsapp":
        try:
            delete_instance(chatbot)
        except EvolutionApiError:
            messages.error(request, "بات حذف نشد؛ حذف Instance از Evolution API ناموفق بود.")
            return redirect("social_media_chatbots")
    chatbot.delete()
    messages.success(request, "بات حذف شد.")
    return redirect("social_media_chatbots")


@login_required
@require_http_methods(["GET", "POST"])
def chatbot_whatsapp_connect(request, chatbot_id):
    chatbot = get_object_or_404(
        Chatbot,
        pk=chatbot_id,
        owner=request.user,
        social_media="whatsapp",
    )
    qr_data_url = None
    try:
        if request.method == "POST":
            chatbot.whatsapp_connection_state, qr_data_url = connect_instance(chatbot)
            chatbot.evolution_webhook_configured = True
        else:
            chatbot.whatsapp_connection_state = connection_state(chatbot)
        chatbot.save(update_fields=[
            "whatsapp_connection_state",
            "evolution_webhook_configured",
            "updated_at",
        ])
    except EvolutionApiError:
        chatbot.whatsapp_connection_state = "error"
        chatbot.evolution_webhook_configured = False
        chatbot.save(update_fields=[
            "whatsapp_connection_state",
            "evolution_webhook_configured",
            "updated_at",
        ])
        messages.warning(request, "وضعیت یا QR از Evolution API دریافت نشد؛ تنظیمات اتصال سرور را بررسی کن.")
    response = render(
        request,
        "dashboard/chatbot_whatsapp_connect.html",
        {"chatbot": chatbot, "qr_data_url": qr_data_url},
    )
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    return response
