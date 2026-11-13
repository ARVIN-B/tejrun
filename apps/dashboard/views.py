from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from apps.agents.models import Chatbot


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)

            return redirect("dashboard")

        error = "نام کاربری یا رمز عبور اشتباه است."

    return render(
        request,
        "dashboard/login.html",
        {
            "error": error,
        },
    )


@login_required
def dashboard_view(request):
    return render(
        request,
        "dashboard/dashboard.html",
        {
            "social_chatbots": Chatbot.objects.filter(
                owner=request.user,
                is_active=True,
            )
            .only("id", "name", "social_media", "is_active")
            .order_by("name"),
        },
    )

@login_required
def logout_view(request):
    logout(request)

    return redirect("login")
