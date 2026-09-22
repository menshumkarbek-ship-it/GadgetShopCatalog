from django.core.cache import cache

CONTACT_SETTINGS_CACHE_KEY = 'global_contact_settings'
SITE_IDENTITY_CACHE_KEY = 'global_site_identity'
# Deliberately short. The signals in signals.py clear these on save, but the
# cache backend is per-process (LocMemCache), so that only reaches the worker
# that handled the edit — on a multi-worker deploy the others keep serving the
# old value until it expires. A minute is long enough to collapse the repeated
# per-request queries and short enough that a stale phone number on the Contact
# page is never something anyone notices.
SETTINGS_CACHE_TIMEOUT = 60


def is_admin(request):
    """Expose whether the current visitor is staff/manager, for nav rendering."""
    if not request.user.is_authenticated:
        return {'is_admin_user': False}
    is_admin_user = request.user.is_staff or request.user.is_superuser or request.user.groups.filter(
        name__in=['Admins', 'Managers']
    ).exists()
    return {'is_admin_user': is_admin_user}


def contact_settings(request):
    """
    Expose the store's admin-managed contact channels to every template.

    Cached: this runs on every request, and get_solo() is a get_or_create,
    so leaving it uncached costs a query (and a write on first hit) per page
    view for a row that changes maybe monthly.
    """
    from .models import ContactSettings

    settings_obj = cache.get(CONTACT_SETTINGS_CACHE_KEY)
    if settings_obj is None:
        settings_obj = ContactSettings.get_solo()
        cache.set(CONTACT_SETTINGS_CACHE_KEY, settings_obj, SETTINGS_CACHE_TIMEOUT)
    return {'contact_settings': settings_obj}


def site_identity(request):
    """
    Expose the admin-editable store/market name to every template (navbar,
    browser tab titles, footer).

    Named `store_name` (not `site_name`) deliberately: Django's own
    django.contrib.auth.views.LoginView — used by the admin login page —
    unconditionally injects its own `site_name` context variable sourced
    from django.contrib.sites (defaults to "example.com"), which would
    silently shadow ours on that page if we reused the same key.

    The cached value is the resolved name for the active language, so the
    key is per-language rather than global.
    """
    from django.utils.translation import get_language
    from .models import AboutPageContent

    cache_key = f'{SITE_IDENTITY_CACHE_KEY}:{get_language() or "en"}'
    store_name = cache.get(cache_key)
    if store_name is None:
        store_name = AboutPageContent.get_solo().translated_site_name
        cache.set(cache_key, store_name, SETTINGS_CACHE_TIMEOUT)
    return {'store_name': store_name}


# Every view that renders inside the management panel's sidebar layout. The
# panel is also reachable at /admin/, which resolves to the same view as
# shop:create_product under the name `admin_panel`.
MANAGEMENT_URL_NAMES = frozenset({
    'management_home', 'create_product', 'update_product', 'create_category',
    'removed_products', 'manage_homepage', 'manage_about', 'manage_contacts',
    'sales_report', 'sales_archive',
})


def management_nav(request):
    """
    The management panel's sidebar: its grouped links, and the counts on them.

    Built here rather than spelled out in the template because the panel
    renders this list twice — stacked in the desktop sidebar, and inside a
    collapsible disclosure on phones, which also has to name the section the
    admin is currently on. One list means those can't drift apart, and adding
    a page to the panel is one entry here.

    Which entry is lit is NOT decided here: each view passes its own `active`
    key (see _management_nav_item.html), so the page itself stays the
    authority on where the admin is.

    Scoped to management pages by url_name rather than by path, so it holds
    whatever those URLs are mounted at — and so the storefront never pays a
    query for a sidebar it doesn't render. resolver_match is set on the
    request before the view runs, and context processors run at render time,
    so it is always populated by the time this is asked.
    """
    match = getattr(request, 'resolver_match', None)
    if match is None or match.url_name not in MANAGEMENT_URL_NAMES:
        return {}

    from django.urls import reverse
    from django.utils.translation import gettext as _

    from .models import Product

    removed_count = Product.all_objects.filter(deleted_at__isnull=False).count()

    return {
        'removed_count': removed_count,
        'management_groups': [
            {
                'label': _('Catalog'),
                'items': [
                    {'key': 'products', 'label': _('Products'), 'icon': 'fa-box',
                     'url': reverse('shop:create_product')},
                    {'key': 'categories', 'label': _('Categories'), 'icon': 'fa-tags',
                     'url': reverse('shop:create_category')},
                    {'key': 'removed', 'label': _('Removed'), 'icon': 'fa-trash-can',
                     'url': reverse('shop:removed_products'), 'badge': removed_count},
                ],
            },
            {
                'label': _('Sales'),
                'items': [
                    # One entry: the page carries its own month / all-time
                    # switch, and opens on all time, which is the view
                    # staff actually read.
                    {'key': 'sales', 'label': _('Sales'), 'icon': 'fa-chart-line',
                     'url': reverse('shop:sales_archive')},
                ],
            },
            {
                'label': _('Pages'),
                'items': [
                    {'key': 'homepage', 'label': _('Homepage'), 'icon': 'fa-house',
                     'url': reverse('shop:manage_homepage')},
                    {'key': 'about', 'label': _('About Page'), 'icon': 'fa-file-lines',
                     'url': reverse('shop:manage_about')},
                    {'key': 'contacts', 'label': _('Contacts'), 'icon': 'fa-address-book',
                     'url': reverse('shop:manage_contacts')},
                ],
            },
        ],
    }
