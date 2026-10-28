from django.contrib import admin
from django.urls import include, path
from accounts.views import entry

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('barter_details.urls')),
    path('add_items/', include('add_items.urls')),
    path('accounts/', include('accounts.urls')),
    path('posts/', include('profile_post.urls')),
    path('keranjang/', include('keranjang.urls')),
    path('', include('core.urls')),
    path('landing/', include('main_page.urls')),
    path('', entry, name='home'),
]
