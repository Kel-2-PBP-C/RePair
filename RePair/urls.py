from django.contrib import admin
from django.urls import include, path
from accounts.views import entry

urlpatterns = [
    path('admin/', admin.site.urls),
<<<<<<< HEAD
    path('', include('barter_details.urls')),
    path('add_items/', include('add_items.urls')),
]
=======
    path('barter-details/', include('barter_details.urls')),
    path('accounts/', include('accounts.urls')),
    path('posts/', include('profile_post.urls')),
    path('keranjang/', include('keranjang.urls')),
    path('', include('core.urls')),
    path('landing/', include('main_page.urls')),
    path('', entry, name='home'),
]
>>>>>>> 7c31ac4f2ecd7f780455fe3cea0402194bb0c748
