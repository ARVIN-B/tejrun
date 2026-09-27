from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


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
    )

@login_required
def logout_view(request):
    logout(request)

    return redirect("login")


@login_required
def social_media_chatbots_view(request):
    chatbots = [
        {
            "id": 1,
            "name": "Tejrun Support",
            "model": "GPT-OSS 120B",
            "prompt": (
                "You are the official customer support assistant "
                "for Tejrun. Answer users clearly and professionally..."
            ),
            "active": True,
        },
        {
            "id": 2,
            "name": "Instagram Assistant",
            "model": "GPT-OSS 120B",
            "prompt": (
                "You are a social media assistant responsible for "
                "answering Instagram users and maintaining..."
            ),
            "active": True,
        },
        {
            "id": 3,
            "name": "Sales Assistant",
            "model": "DeepSeek V3",
            "prompt": (
                "You are a sales assistant. Help customers understand "
                "products, prices and available services..."
            ),
            "active": False,
        },
    ]

    return render(
        request,
        "dashboard/social_media_chatbots.html",
        {
            "chatbots": chatbots,
        },
    )