from django.urls import path
from . import views

app_name = 'add_items'

urlpatterns = [
    path('new/', views.create_barter, name='create'),
    path('new/submit/', views.create_barter_ajax, name='create_ajax')
]
