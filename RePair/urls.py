from django.contrib import admin
from django.urls import include, path
from accounts.views import entry

urlpatterns = [
    path('admin/', admin.site.urls),
    path('barter-details/', include('barter_details.urls')),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
    path('', entry, name='home'),
]
