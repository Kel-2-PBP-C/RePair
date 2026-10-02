from django.shortcuts import render

# Create your views here.

def show_profile(request):
    context = {}
    return render(request, "profile_post/index.html", context)
