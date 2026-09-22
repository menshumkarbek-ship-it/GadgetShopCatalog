from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .context_processors import CONTACT_SETTINGS_CACHE_KEY, SITE_IDENTITY_CACHE_KEY
from .models import Category, ContactSettings, HomePageContent


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, **kwargs):
    """Keep the cached category list fresh so a new category (and its
    homepage slideshow / catalog filter option) appears immediately,
    regardless of whether it was created via the branded form or admin."""
    cache.delete('global_store_categories')


@receiver(post_save, sender=ContactSettings)
def invalidate_contact_settings_cache(sender, **kwargs):
    """Contact channels are cached per request in a context processor, so an
    edit has to clear it or the Contact page keeps showing the old number."""
    cache.delete(CONTACT_SETTINGS_CACHE_KEY)


@receiver(post_save, sender=HomePageContent)
def invalidate_site_identity_cache(sender, **kwargs):
    """The store name is cached per active language, so renaming the store
    has to clear every language's entry, not just the current one."""
    cache.delete_many([
        f'{SITE_IDENTITY_CACHE_KEY}:{code}' for code, _ in settings.LANGUAGES
    ])
