from django.contrib import admin
from django.urls import include, path
from accounts.views import entry

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('barter_details.urls')),
    path('add_items/', include('add_items.urls')),
]
