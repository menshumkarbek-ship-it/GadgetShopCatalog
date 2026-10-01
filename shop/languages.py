"""
Which languages are switched on (see models.LanguageSettings).

Read on every request by the language middleware and the navbar switcher, so
the answer is cached briefly, and the cache is cleared when the settings are
saved (signals.py).
"""
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

CACHE_KEY = 'site_enabled_languages'
# Short, like the other site-wide settings: the worker that saved the change
# sees it at once, the others within a minute.
CACHE_TIMEOUT = 60


def all_codes():
    return [code for code, _name in settings.LANGUAGES]


def enabled_languages():
    """Codes of the languages visitors may use, in switcher order."""
    codes = cache.get(CACHE_KEY)
    if codes is None:
        from .models import LanguageSettings
        try:
            codes = LanguageSettings.get_solo().enabled_codes
        except DatabaseError:
            # Before the table exists (a fresh deploy mid-migration).
            return all_codes()
        cache.set(CACHE_KEY, codes, CACHE_TIMEOUT)
    return codes


def default_language(codes=None):
    """The language a visitor gets until they pick one: the site's preferred
    default (settings.LANGUAGE_CODE) if it is on, otherwise the first that is."""
    codes = codes or enabled_languages()
    return settings.LANGUAGE_CODE if settings.LANGUAGE_CODE in codes else codes[0]
