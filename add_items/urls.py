from django.urls import path
from . import views

app_name = 'add_items'

urlpatterns = [
    path('new/', views.create_barter, name='create'),
    path('new/submit/', views.create_barter_ajax, name='create_ajax'),
    path('<uuid:pk>/edit/', views.edit_barter, name='edit'),
    path('<uuid:pk>/edit_ajax/', views.edit_barter_ajax, name='edit_ajax'),
    path('<uuid:pk>/delete', views.delete_barter_ajax, name='delete')
]
