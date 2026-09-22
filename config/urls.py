from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.contrib.sitemaps.views import sitemap
from shop.sitemaps import StaticViewSitemap
from shop import views as shop_views

sitemaps = {
    'static': StaticViewSitemap,
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

urlpatterns = [
    # 🛠 /admin/ opens the in-app Settings hub (same view as
    # shop:create_product) — this is the URL the shop owner uses day to day.
    path('admin/', shop_views.create_product, name='admin_panel'),

    # 🔒 Django admin, mounted at settings.ADMIN_URL rather than /admin/.
    # Used for user/group management and superuser work only.
    path(settings.ADMIN_URL, admin.site.urls),
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # 🌐 Built-in Django route to handle language-switching form submissions
    path('i18n/', include('django.conf.urls.i18n')),

    # 🏪 Shop Application URLs
    path('', include('shop.urls', namespace='shop')),
]

# Serve media files locally during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)