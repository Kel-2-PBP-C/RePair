from rest_framework.routers import DefaultRouter

from .api_views import ProfilePostViewSet

app_name = 'profile_post_api'

router = DefaultRouter()
router.register('posts', ProfilePostViewSet, basename='posts')

urlpatterns = router.urls
