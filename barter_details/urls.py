from django.urls import path
from . import views

app_name = 'barter_details'

urlpatterns = [
<<<<<<< HEAD
    path('barter/<uuid:pk>/', views.barter_detail, name='barter_detail'),
    path('barter/<uuid:pk>/bid/', views.submit_bid_ajax, name='submit_bid_ajax'),
]
=======
    path('<uuid:pk>/', views.barter_detail, name='barter_detail'),
]
>>>>>>> 7c31ac4f2ecd7f780455fe3cea0402194bb0c748
