from django.urls import path
from . import views

app_name = 'barter_details'

urlpatterns = [
    path('barter/<uuid:pk>/', views.barter_detail, name='barter_detail'),
    path('barter/<uuid:pk>/bid/', views.submit_bid_ajax, name='submit_bid_ajax'),
    path('<uuid:pk>/delete', views.delete_barter_ajax, name='delete_ajax')
]
