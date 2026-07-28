from rest_framework.routers import DefaultRouter

from . import views

app_name = "orders_api"

router = DefaultRouter()
router.register("", views.OrderViewSet, basename="order")

urlpatterns = router.urls
