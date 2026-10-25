from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from barter_details.models import Barter


#@login_required
@require_GET
def show_main(request):
    items = Barter.objects.all()

    context = {
        'items': items,
    }

    return render(request, "main_page/main_page.html", context)