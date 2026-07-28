from rest_framework.routers import DefaultRouter

from . import views

app_name = "products_api"

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("", views.ProductViewSet, basename="product")

urlpatterns = router.urls
