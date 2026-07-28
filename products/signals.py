from django.core.cache import cache
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category, Product


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_category_cache_on_category_change(sender, **kwargs):
    cache.delete(settings.CATEGORY_TREE_CACHE_KEY)


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_category_cache_on_product_change(sender, **kwargs):
    # Product changes don't alter the tree shape, but recommendations read
    # product state, so we keep this hook available for future product-
    # aware caching (e.g. per-category product count) without needing to
    # touch this signal file again.
    pass
