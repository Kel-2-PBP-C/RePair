from django.urls import path
from . import views

app_name = 'profile_post'

urlpatterns = [
    path('', views.index, name='show_posts'),
    path('<str:post_id>/', views.post_detail_page, name='post_detail'),
    path('api/regions/', views.search_regions_api, name='search_regions'),
    path('api/stats/', views.get_user_stats, name='get_user_stats'),
    path('api/list/', views.get_posts_json, name='get_posts_json'),
    path('api/forum/', views.get_forum_posts_json, name='get_forum_posts'),
    path('api/create/', views.create_post_ajax, name='create_post'),
    path('api/edit/<str:post_id>/', views.edit_post_ajax, name='edit_post'),
    path('api/delete/<str:post_id>/', views.delete_post_ajax, name='delete_post'),
    path('api/offers/<str:post_id>/', views.get_post_offers_json, name='get_post_offers'),
    path('api/lock/<str:post_id>/', views.lock_barter_ajax, name='lock_barter'),
    path('api/cancel-negotiation/<str:post_id>/', views.cancel_negotiation_ajax, name='cancel_negotiation'),
    path('api/complete/<str:post_id>/', views.complete_barter_ajax, name='complete_barter'),
    path('api/review/<str:post_id>/', views.submit_review_ajax, name='submit_review'),
]