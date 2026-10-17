from django.shortcuts import render


def keranjang(request):
    return render(request, 'keranjang/keranjang.html')