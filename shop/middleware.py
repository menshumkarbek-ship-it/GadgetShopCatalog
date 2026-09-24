from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class SiteLanguageMiddleware(LocaleMiddleware):
    """
    Serve every visitor the site's default language (settings.LANGUAGE_CODE,
    Russian) until they pick another one in the navbar switcher.

    Django's own LocaleMiddleware would first try the browser's
    Accept-Language header, so a phone set to English would open the store
    in English. The store is Russian-first, so that header is ignored here:
    only the switcher's cookie can change the language.
    """

    def process_request(self, request):
        language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if not language or not translation.check_for_language(language) \
                or language not in dict(settings.LANGUAGES):
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        # The parent also adds `Vary: Accept-Language`, which no longer
        # changes the page — only the cookie does, and Vary: Cookie is
        # already set by the session and CSRF machinery.
        response.headers.setdefault('Content-Language', translation.get_language())
        return response
