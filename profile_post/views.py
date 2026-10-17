from django.shortcuts import render


def show_posts(request):
    return render(request, "profile_post/index.html")
