from django.urls import path
from . import views

app_name = 'barter_details'

urlpatterns = [
    path('<uuid:pk>/', views.barter_detail, name='barter_detail'),
]
