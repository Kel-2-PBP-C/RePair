from django.urls import path
from . import views

app_name = 'profile_post'

urlpatterns = [
    path('', views.show_posts_page, name='show_posts'),
    path('api/stats/', views.get_user_stats, name='get_user_stats'),
    path('api/list/', views.get_posts_json, name='get_posts_json'),
    path('api/create/', views.create_post_ajax, name='create_post'),
    path('api/edit/<int:post_id>/', views.edit_post_ajax, name='edit_post'),
    path('api/delete/<int:post_id>/', views.delete_post_ajax, name='delete_post'),
]