from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def login(request):
    return render(request, "accounts/login.html")


@require_GET
def register(request):
    return render(request, "accounts/register.html")


@require_GET
def profile(request):
    return render(request, "accounts/profile.html")


@require_GET
def settings(request):
    return render(request, "accounts/settings.html")
