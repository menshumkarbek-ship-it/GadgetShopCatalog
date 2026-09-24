from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.templatetags.static import static as static_url
from django.contrib.sitemaps.views import sitemap
from shop.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap
from shop import views as shop_views

sitemaps = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
}

def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.ADMIN_URL}",
        "Disallow: /admin/",
        "Disallow: /management/",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def favicon(request):
    """Browsers and crawlers ask for /favicon.ico whatever the <link> tags
    say; without this every first visit logs a 404. Resolved per request so
    the hashed name from the static manifest is used."""
    return HttpResponsePermanentRedirect(static_url('shop/favicon.ico'))


urlpatterns = [
    # 🛠 /admin/ opens the in-app Settings hub (same view as
    # shop:create_product) — this is the URL the shop owner uses day to day.
    path('admin/', shop_views.create_product, name='admin_panel'),

    # 🔒 Django admin, mounted at settings.ADMIN_URL rather than /admin/.
    # Used for user/group management and superuser work only.
    path(settings.ADMIN_URL, admin.site.urls),
    path('robots.txt', robots_txt),
    path('favicon.ico', favicon),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # 🌐 Built-in Django route to handle language-switching form submissions
    path('i18n/', include('django.conf.urls.i18n')),

    # 🏪 Shop Application URLs
    path('', include('shop.urls', namespace='shop')),
]

# Serve media files locally during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)