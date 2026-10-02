from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
@require_GET
def show_main(request):
    return render(request, "main_page.html")
