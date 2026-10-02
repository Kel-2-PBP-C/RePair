from django.urls import path
from . import views

urlpatterns = [
    path('', views.keranjang, name='keranjang'),
]