from django.contrib import admin
from django.urls import include, path
from accounts.views import entry

urlpatterns = [
    path('admin/', admin.site.urls),
    path('barter-details/', include('barter_details.urls')),
    path('accounts/', include('accounts.urls')),
    path(
        'api/profile-post/',
        include(('profile_post.api_urls', 'profile_post_api'), namespace='profile_post_api'),
    ),
    path('posts/', include('profile_post.urls')),
    path('keranjang/', include('keranjang.urls')),
    path('', include('core.urls')),
    path('landing/', include('main_page.urls')),
    path('', entry, name='home'),
]
