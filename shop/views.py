from datetime import date, timedelta

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db.models import Q, Sum, Count, Min, Max
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from .models import (
    Product, Category, ProductImage, ContactSettings, AboutPageContent, HomePageContent, Sale,
)
from .forms import (
    ProductCreateForm, CategoryCreateForm, ContactSettingsForm, AboutPageContentForm,
    HomePageContentForm,
)

CATEGORIES_CACHE_KEY = 'global_store_categories'
# Short on purpose — see the note on SETTINGS_CACHE_TIMEOUT in
# context_processors: the cache is per-process, so the post_save signal that
# clears it only reaches one worker and the rest must expire on their own. A
# new category appearing in the filter a minute late is fine; fifteen is not.
CATEGORIES_CACHE_TIMEOUT = 60


def get_cached_categories():
    categories = cache.get(CATEGORIES_CACHE_KEY)
    if not categories:
        categories = list(Category.objects.all())
        cache.set(CATEGORIES_CACHE_KEY, categories, CATEGORIES_CACHE_TIMEOUT)
    return categories


# ==========================================
# 🏠 HOME PAGE CONTROLLER
# ==========================================

def home_page(request):
    categories = get_cached_categories()

    # Both sections below want "the newest in-stock products, per category".
    # Fetching that once and grouping in Python keeps the page at a fixed
    # query count instead of one query per category, twice over.
    newest_by_category = {}
    for product in Product.objects.filter(is_sold=False).select_related('category').order_by('-created_at', '-id'):
        newest_by_category.setdefault(product.category_id, []).append(product)

    # 🆕 Hero announcement slides: an admin marks a category as "featured in
    # hero" (from the Categories management page) and its newest in-stock
    # product becomes an auto-rotating slide here. No fixed slide count.
    hero_slides = []
    featured_categories = [c for c in categories if c.is_featured_in_hero]
    for category in sorted(featured_categories, key=lambda c: c.name):
        products = newest_by_category.get(category.id)
        if products:
            hero_slides.append({'category': category, 'product': products[0]})

    # Whatever the hero is already showing is skipped in the rows below —
    # otherwise the first card of each row is the slide directly above it.
    hero_product_ids = {slide['product'].id for slide in hero_slides}

    # 🆕 Build one "Newest In <Category>" slideshow row per category that has
    # stock AND that an admin has left switched on (Category.show_newest_row,
    # toggled from the Categories management page). New categories default to
    # shown, so this stays fully data-driven unless an admin opts a category out.
    category_sections = []
    for category in categories:
        if not category.slug or not category.show_newest_row:
            continue
        products = [
            p for p in newest_by_category.get(category.id, [])
            if p.id not in hero_product_ids
        ][:10]
        if products:
            category_sections.append({'category': category, 'products': products})

    context = {
        'categories': categories,
        'hero_slides': hero_slides,
        'category_sections': category_sections,
        # Counted off the grouping above rather than a second COUNT query.
        'in_stock_count': sum(len(items) for items in newest_by_category.values()),
        # The two editorial bands wrapped around the rows above. Staff
        # write them on the Homepage tab of the management panel; the
        # rows themselves come from the catalog and have no copy to set.
        'homepage': HomePageContent.get_solo(),
    }
    return render(request, 'shop/home.html', context)


# ==========================================
# 🏪 CATALOG CONTROLLER
# ==========================================

def product_list(request, category_slug=None):
    category = None
    categories = get_cached_categories()

    products_list = Product.objects.filter(is_sold=False).select_related('category').order_by('-id')

    # The dropdown submits real category slugs, so keep the incoming value
    # untouched for re-selecting the option and building pagination links;
    # only `type_filter` below gets rewritten for the query.
    selected_type = request.GET.get('type') or category_slug or ''
    type_filter = selected_type

    # Old links used plural slugs that no longer exist as categories. Remap
    # them only when the value isn't a real slug, otherwise a current slug
    # like "laptops" would be rewritten to "laptop" and stop matching exactly.
    legacy_type_aliases = {'phones': 'phone', 'laptops': 'laptop', 'tablets': 'tablet'}
    if type_filter in legacy_type_aliases and type_filter not in {c.slug for c in categories}:
        type_filter = legacy_type_aliases[type_filter]

    brand_filter = request.GET.get('brand')
    search_query = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    has_active_filters = bool(type_filter or brand_filter or search_query or min_price or max_price)

    if type_filter:
        products_list = products_list.filter(
            Q(category__slug__iexact=type_filter) | Q(category__name__icontains=type_filter)
        )

    if brand_filter:
        products_list = products_list.filter(brand__iexact=brand_filter)

    if search_query:
        products_list = products_list.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if min_price:
        try:
            products_list = products_list.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products_list = products_list.filter(price__lte=float(max_price))
        except ValueError:
            pass

    available_brands = Product.objects.filter(is_sold=False).order_by('brand').values_list('brand', flat=True).distinct()

    # Real catalog bounds, so the price inputs hint at what the store actually
    # stocks instead of a hardcoded range nothing falls into.
    price_bounds = Product.objects.filter(is_sold=False).aggregate(low=Min('price'), high=Max('price'))

    # The whole matching catalog on one page: the store owner wants every
    # product visible at once, and at this catalog size (well under a few
    # hundred rows) one query is cheaper than a pager anyone has to click.
    products = list(products_list.distinct())

    context = {
        'category': category,
        'categories': categories,
        'products': products,
        'available_brands': available_brands,
        'price_floor': price_bounds['low'],
        'price_ceiling': price_bounds['high'],
        'selected_type': selected_type,
        'selected_brand': brand_filter or '',
        'min_price': min_price or '',
        'max_price': max_price or '',
        'search_query': search_query or '',
        'has_active_filters': has_active_filters,
    }
    return render(request, 'shop/product/list.html', context)


def product_detail(request, product_slug):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('gallery_images'),
        slug=product_slug, is_sold=False
    )

    related_products = list(
        Product.objects.filter(is_sold=False, category=product.category)
        .exclude(pk=product.pk)
        .select_related('category')
        .order_by('-created_at', '-id')[:8]
    )

    context = {
        'product': product,
        'related_products': related_products,
        'meta_description': product.translated_description or _(
            "%(brand)s %(name)s — available in store."
        ) % {'brand': product.brand, 'name': product.translated_name},
        'og_title': f'{product.brand} {product.translated_name}',
        'og_image': request.build_absolute_uri(product.image.url) if product.image else None,
    }
    return render(request, 'shop/product/detail.html', context)


def product_specs(request, product_slug):
    product = get_object_or_404(Product.objects.select_related('category'), slug=product_slug, is_sold=False)
    return render(request, 'shop/product/specs.html', {'product': product})


# ==========================================
# 📄 AUXILIARY PAGES
# ==========================================

def about_us(request):
    """
    The shop's story, with the catalog itself as the evidence: the figures
    band is counted from live stock, so the page never claims a range the
    shelves don't back up.
    """
    # One pass over the in-stock catalog gives all three figures — no
    # separate COUNTs.
    categories_in_stock = set()
    brands = set()
    in_stock_count = 0
    for category_id, brand in Product.objects.filter(is_sold=False).values_list('category_id', 'brand'):
        categories_in_stock.add(category_id)
        if brand:
            brands.add(brand.strip().lower())
        in_stock_count += 1

    context = {
        'about': AboutPageContent.get_solo(),
        'in_stock_count': in_stock_count,
        'category_count': len(categories_in_stock),
        'brand_count': len(brands),
    }
    return render(request, 'shop/pages/about.html', context)


def contact_us(request):
    product_slug = request.GET.get('product')
    inquiry_product = None
    if product_slug:
        inquiry_product = Product.objects.filter(slug=product_slug, is_sold=False).select_related('category').first()

    if inquiry_product:
        product_url = request.build_absolute_uri(
            reverse('shop:product_detail', kwargs={'product_slug': inquiry_product.slug})
        )
        inquiry_message = _("Hi! I'm interested in the %(name)s (%(url)s). Is it still available?") % {
            'name': inquiry_product.translated_name, 'url': product_url,
        }
    else:
        product_url = None
        site_name = HomePageContent.get_solo().translated_site_name
        inquiry_message = _("Hi! I have a question about a product at %(site_name)s.") % {'site_name': site_name}

    context = {
        'inquiry_product': inquiry_product,
        'inquiry_product_url': product_url,
        'inquiry_message': inquiry_message,
    }
    return render(request, 'shop/pages/contact.html', context)


# ==========================================
# 🛠️ CATALOG MANAGEMENT (staff/manager only, via Django admin login)
# ==========================================

def _wants_json(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _panel_response(request, redirect_response, ok=True, **payload):
    """
    Every action in the management panel is posted in the background by the
    panel's script, so the page updates in place instead of reloading. Those
    posts are answered with JSON: whether it worked, the flash messages to
    show (consumed here so they don't reappear on the next full page), and
    whatever the page needs to update itself — a rendered row, a count.

    A plain post — no script, or JavaScript off — gets the redirect the
    panel always used, so nothing depends on the script being there.
    """
    if not _wants_json(request):
        return redirect_response
    flashes = [{'level': message.level_tag, 'text': str(message)} for message in messages.get_messages(request)]
    return JsonResponse({'ok': ok, 'messages': flashes, **payload}, status=200 if ok else 400)


def _form_errors(form):
    """A form's errors as the panel script expects them: one entry per
    field, labelled, so it can list them and mark the inputs."""
    return [
        {
            'field': name,
            'label': str(form.fields[name].label or name.replace('_', ' ').title()) if name in form.fields else '',
            'messages': [str(error) for error in errors],
        }
        for name, errors in form.errors.items()
    ]


def _removed_count():
    return Product.all_objects.filter(deleted_at__isnull=False).count()


def is_admin_or_manager(user):
    return user.is_authenticated and (
            user.is_staff or
            user.is_superuser or
            user.groups.filter(name__in=['Admins', 'Managers']).exists()
    )


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def management_home(request):
    """
    The front door of the management panel.

    On a phone this is the whole panel's top level: the section list fills
    the screen, and picking one opens that section on its own (with a Back
    link returning here), the way a settings app drills down. On a desktop
    it is the same sidebar beside an overview of the sections.

    Passes no `active` key on purpose — that is what tells the shell to show
    the list instead of a section (see _management_base.html).
    """
    return render(request, 'shop/product/management_home.html')


# One-click row names for the product form's characteristics section: the
# ones most devices share. Anything else is typed in by hand.
SPEC_PRESETS = [
    gettext_lazy('Model'), gettext_lazy('CPU'), gettext_lazy('RAM'), gettext_lazy('Storage'),
    gettext_lazy('Screen'), gettext_lazy('Camera'), gettext_lazy('Battery'), gettext_lazy('Color'),
]


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def create_product(request, product_id=None):
    product_instance = None
    if product_id:
        product_instance = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        form = ProductCreateForm(request.POST, request.FILES, instance=product_instance)
        if form.is_valid():
            product = form.save()

            # Extra gallery photos: a plain <input type="file" name="extra_images"
            # multiple> isn't a ModelForm field (Django forms don't support
            # multi-file fields out of the box), so they're picked up straight
            # from request.FILES and saved as separate ProductImage rows.
            extra_images = request.FILES.getlist('extra_images')
            if extra_images:
                next_order = product.gallery_images.count()
                for offset, image_file in enumerate(extra_images):
                    ProductImage.objects.create(product=product, image=image_file, order=next_order + offset)

            if product_instance:
                messages.success(request, _("Product successfully updated!"))
            else:
                messages.success(request, _("Product successfully cataloged!"))
            return _panel_response(request, redirect('shop:product_list'))
        else:
            messages.error(request, _("Please correct the entry errors down below."))
            if _wants_json(request):
                return _panel_response(request, None, ok=False, errors=_form_errors(form))
    else:
        form = ProductCreateForm(instance=product_instance)

    # The list is a drill-down: the categories, then — once one is pressed —
    # that category's listings in #ID order, the way the panel itself opens
    # a section. One query for the whole catalog; the grouping, the counts,
    # and the search all happen on that list.
    all_products = Product.objects.filter(is_sold=False).select_related('category').order_by(
        'category__name', 'category_number'
    )
    products_by_category = {}
    for product in all_products:
        products_by_category.setdefault(product.category, []).append(product)
    category_groups = [
        {'category': category, 'products': products}
        for category, products in products_by_category.items()
    ]

    # Which category is open, if any. An unknown slug just shows the list.
    requested_slug = request.GET.get('category', '')
    selected_group = next(
        (group for group in category_groups if group['category'].slug == requested_slug), None
    )

    # Search by catalog #ID (to pull up the exact listing to mark sold), or
    # by name/brand for a more casual lookup. Results come from every
    # category and replace the open category's listings while it's active.
    search_query = request.GET.get('q', '').strip()
    search_groups = None
    if search_query:
        needle = search_query.lower()
        number = int(search_query.lstrip('#')) if search_query.lstrip('#').isdigit() else None
        search_groups = []
        for group in category_groups:
            matches = [
                p for p in group['products']
                if needle in p.name.lower() or needle in p.brand.lower() or p.category_number == number
            ]
            if matches:
                search_groups.append({'category': group['category'], 'products': matches})

    known_brands = Product.objects.exclude(brand='').values_list('brand', flat=True).distinct().order_by('brand')
    gallery_images = product_instance.gallery_images.all() if product_instance else []

    # Removed listings are deliberately not shown here: this page is for
    # what is on sale. Undoing a removal happens on the Removed page.
    context = {
        'form': form,
        'product_instance': product_instance,
        'category_groups': category_groups,
        'selected_group': selected_group,
        'search_query': search_query,
        'search_groups': search_groups,
        'known_brands': known_brands,
        'spec_presets': SPEC_PRESETS,
        'gallery_images': gallery_images,
        'active': 'products',
    }
    return render(request, 'shop/product/create.html', context)


def _sale_for_removal(product):
    """The Sale recorded by the removal that is currently in effect for
    `product`, or None if that removal was a plain delete. Sale.sold_at is
    stamped a moment before deleted_at, hence the small tolerance."""
    if product.deleted_at is None:
        return None
    return Sale.objects.filter(
        product=product, sold_at__gte=product.deleted_at - timedelta(seconds=5),
    ).order_by('-sold_at', '-id').first()


def _annotate_removal_kind(products):
    """
    Set `was_sold` on each removed listing: whether the removal currently
    in effect recorded a sale, or was a plain delete. Resolves the whole
    list in one query — _sale_for_removal() is the single-row version and
    would cost a query per listing on a page showing every removal.
    """
    products = list(products)
    if not products:
        return products

    sales_by_product = {}
    for sale in Sale.objects.filter(product__in=products).only('product_id', 'sold_at'):
        sales_by_product.setdefault(sale.product_id, []).append(sale.sold_at)

    for product in products:
        # Same five-second tolerance as _sale_for_removal: Sale.sold_at is
        # stamped a moment before deleted_at.
        cutoff = product.deleted_at - timedelta(seconds=5) if product.deleted_at else None
        product.was_sold = cutoff is not None and any(
            sold_at >= cutoff for sold_at in sales_by_product.get(product.id, ())
        )
    return products


def _after_catalog_action(request):
    """
    Where to land after removing, restoring, or deleting a listing. Both
    the Products page and the Removed page offer these, so each posts its
    own `next` and the admin stays on the page they acted from — and, on
    the Products page, in the category they acted from.
    """
    destinations = {'removed': 'shop:removed_products', 'products': 'shop:create_product'}
    url = reverse(destinations.get(request.POST.get('next'), 'shop:create_product'))
    category_slug = request.POST.get('category', '')
    if category_slug and request.POST.get('next') != 'removed':
        url += '?' + urlencode({'category': category_slug})
    return redirect(url)


def _remove_from_catalog(product):
    # Soft delete: the row and its photos stay, so a mis-click can be undone
    # from the Removed page instead of being gone for good.
    product.deleted_at = timezone.now()
    product.save(update_fields=['deleted_at'])


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def sell_product(request, product_id):
    """
    The listing sold in the physical store — there is no checkout flow —
    so snapshot it as a Sale and take it off the catalog. The snapshot uses
    the values as they are right now, so later edits never change a past
    month's sales report.
    """
    product = get_object_or_404(Product.objects.select_related('category'), id=product_id)

    Sale.objects.create(
        product=product,
        product_name=product.name,
        brand=product.brand,
        category_name=product.category.name,
        catalog_code=product.catalog_code,
        price=product.price,
        sold_by=request.user,
    )
    _remove_from_catalog(product)

    messages.success(
        request,
        _('"%(name)s" was marked as sold and removed from the catalog. You can undo this from "Removed".')
        % {'name': product.name},
    )
    return _panel_response(request, _after_catalog_action(request), removed_count=_removed_count())


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def remove_product(request, product_id):
    """
    Take a listing off the catalog without recording a sale — for items
    added by mistake, duplicates, or stock that left some other way.
    """
    product = get_object_or_404(Product.objects, id=product_id)
    _remove_from_catalog(product)

    messages.success(
        request,
        _('"%(name)s" was removed from the catalog (not counted as a sale). You can undo this from "Removed".')
        % {'name': product.name},
    )
    return _panel_response(request, _after_catalog_action(request), removed_count=_removed_count())


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def restore_product(request, product_id):
    """
    Undo a removal: puts the listing back in the catalog and, if that
    removal was recorded as a sale, drops the Sale row too, so the monthly
    report doesn't keep counting a sale that never happened.
    """
    product = get_object_or_404(Product.all_objects, id=product_id, deleted_at__isnull=False)

    sale = _sale_for_removal(product)
    if sale:
        sale.delete()

    product.deleted_at = None
    product.save(update_fields=['deleted_at'])

    messages.success(request, _('"%(name)s" is back in the catalog.') % {'name': product.name})
    return _panel_response(request, _after_catalog_action(request), removed_count=_removed_count())


def _delete_product_files(product):
    """Erase the image files behind a product; nothing else cleans them up, so
    deleting only the rows would leave them orphaned in media/."""
    for photo in product.gallery_images.all():
        photo.image.delete(save=False)
    if product.image:
        product.image.delete(save=False)


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def purge_product(request, product_id):
    """
    Delete a removed listing for good: the row, its gallery rows, and the
    image files behind them, which nothing else cleans up.

    Only reachable for a listing already sitting in "Removed", so a
    permanent delete always costs two deliberate clicks. Any Sale it recorded
    is deliberately left standing — Sale.product is SET_NULL and every figure
    the report reads is snapshotted on the Sale itself, so past months keep
    their revenue. Use "Discard" on the report to strike a sale.
    """
    product = get_object_or_404(Product.all_objects, id=product_id, deleted_at__isnull=False)

    name = product.name
    _delete_product_files(product)
    product.delete()

    messages.success(
        request,
        _('"%(name)s" was permanently deleted, along with its photos.') % {'name': name},
    )
    return _panel_response(request, _after_catalog_action(request), removed_count=_removed_count())


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def delete_category(request, category_id):
    """
    Delete a category and everything filed under it.

    Product.category cascades, so the listings go with it — including any
    parked in "Removed", which stop being restorable. Their image
    files are erased first, since the cascade only takes the rows. Sales
    already recorded survive: Sale.product is SET_NULL and the report reads
    the snapshot on the Sale itself.
    """
    category = get_object_or_404(Category, id=category_id)

    products = list(Product.all_objects.filter(category=category).prefetch_related('gallery_images'))
    for product in products:
        _delete_product_files(product)

    name = category.name
    category.delete()

    messages.success(
        request,
        _('Category "%(name)s" was deleted, along with its products: %(count)s.')
        % {'name': name, 'count': len(products)},
    )
    return _panel_response(request, redirect('shop:create_category'), category_count=Category.objects.count(), removed_count=_removed_count())


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def discard_sale(request, sale_id):
    """
    Strike a row from the sales report — the product was marked sold by
    mistake. The product itself stays removed; restore it from "Removed"
    if it should be back on sale.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    sale.delete()
    messages.success(
        request,
        _('"%(name)s" was struck from the sales report.') % {'name': sale.product_name},
    )
    if request.POST.get('period') == 'all':
        # Struck from the all-time view, so go back to it rather than
        # dropping the admin into whatever month the sale happened to be in.
        return _panel_response(request, redirect('shop:sales_archive'))

    url = reverse('shop:sales_report')
    month, year = request.POST.get('month'), request.POST.get('year')
    if month and year:
        url += f'?month={month}&year={year}'
    return _panel_response(request, redirect(url))


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def delete_product_image(request, image_id):
    gallery_image = get_object_or_404(ProductImage, id=image_id)
    product_id = gallery_image.product_id
    gallery_image.image.delete(save=False)
    gallery_image.delete()
    messages.success(request, _("Photo removed from the gallery."))
    return _panel_response(request, redirect('shop:update_product', product_id=product_id))


def _category_row_html(request, category_id):
    """One row of the Categories list, freshly rendered — what a background
    create or toggle hands back so the page can drop it in."""
    category = Category.objects.annotate(product_count=Count('products')).get(pk=category_id)
    return render_to_string('shop/product/_category_row.html', {'cat': category}, request=request)


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def create_category(request):
    if request.method == 'POST':
        form = CategoryCreateForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, _("Category created! It now appears in the catalog filter and will get its own homepage row once it has products."))
            return _panel_response(
                request, redirect('shop:create_category'),
                html=_category_row_html(request, category.id), category_count=Category.objects.count(),
            )
        else:
            messages.error(request, _("Please correct the entry errors down below."))
            if _wants_json(request):
                return _panel_response(request, None, ok=False, errors=_form_errors(form))
    else:
        form = CategoryCreateForm()

    # Counts every row the cascade would take, removed listings included, so
    # the delete button can say up front why it is unavailable.
    all_categories = Category.objects.annotate(
        product_count=Count('products')
    ).order_by('name')

    context = {
        'form': form,
        'all_categories': all_categories,
        'active': 'categories',
    }
    return render(request, 'shop/product/category_create.html', context)


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def toggle_category_hero(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.is_featured_in_hero = not category.is_featured_in_hero
    category.save(update_fields=['is_featured_in_hero'])

    if category.is_featured_in_hero:
        messages.success(request, _('"%(name)s" added to the homepage announcement slideshow.') % {'name': category.name})
    else:
        messages.success(request, _('"%(name)s" removed from the homepage announcement slideshow.') % {'name': category.name})
    return _panel_response(request, redirect('shop:create_category'), html=_category_row_html(request, category.id))


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
@require_POST
def toggle_category_newest(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.show_newest_row = not category.show_newest_row
    category.save(update_fields=['show_newest_row'])

    if category.show_newest_row:
        messages.success(request, _('"%(name)s" now has a "Newest In" row on the homepage.') % {'name': category.name})
    else:
        messages.success(request, _('"%(name)s"\'s "Newest In" row is hidden from the homepage.') % {'name': category.name})
    return _panel_response(request, redirect('shop:create_category'), html=_category_row_html(request, category.id))


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def manage_contacts(request):
    """
    Lets staff/managers edit the store's WhatsApp, Telegram, Instagram,
    phone, and email contact channels from inside the app itself, so this
    everyday task no longer needs the separate Django admin panel.
    """
    settings_obj = ContactSettings.get_solo()

    if request.method == 'POST':
        form = ContactSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Contact channels updated!"))
            return _panel_response(request, redirect('shop:manage_contacts'))
        else:
            messages.error(request, _("Please correct the entry errors below."))
            if _wants_json(request):
                return _panel_response(request, None, ok=False, errors=_form_errors(form))
    else:
        form = ContactSettingsForm(instance=settings_obj)

    return render(request, 'shop/product/contact_settings.html', {'form': form, 'active': 'contacts'})


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def manage_about(request):
    """
    Lets staff/managers write the About Us page copy — the shop's story,
    market, visit-us details, and address — from inside the app itself.
    """
    content_obj = AboutPageContent.get_solo()

    if request.method == 'POST':
        form = AboutPageContentForm(request.POST, request.FILES, instance=content_obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("About page updated!"))
            return _panel_response(request, redirect('shop:manage_about'))
        else:
            messages.error(request, _("Please correct the entry errors below."))
            if _wants_json(request):
                return _panel_response(request, None, ok=False, errors=_form_errors(form))
    else:
        form = AboutPageContentForm(instance=content_obj)

    # One row per language, each holding that language's variant of every
    # translatable field in a fixed order the template loops over — lets the
    # template render one shared block per language instead of tripling the
    # markup for English/Russian/Kyrgyz by hand.
    about_lang_fields = [
        (
            lang,
            form[f'badge_text{suffix}'], form[f'heading{suffix}'],
            form[f'intro_text{suffix}'], form[f'visit_heading{suffix}'], form[f'visit_text{suffix}'],
            form[f'store_address_line1{suffix}'], form[f'store_address_line2{suffix}'],
            form[f'opening_hours{suffix}'],
            form[f'cta_heading{suffix}'], form[f'cta_text{suffix}'],
        )
        for lang, suffix in [('en', ''), ('ru', '_ru'), ('ky', '_ky')]
    ]

    return render(request, 'shop/product/about_settings.html', {
        'form': form, 'about_lang_fields': about_lang_fields, 'active': 'about',
    })


@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def sales_report(request, period='month'):
    """
    One sales page answering both questions staff ask of it: "how did this
    month go", and "when did we sell that". Both read the same Sale rows —
    created when a product is marked sold, which is how a sale gets recorded
    here since the store has no checkout flow — so the monthly figures and
    the full history can never disagree.

    `period` is 'month' (filtered by the month/year pickers) or 'all' (every
    sale ever recorded); shop:sales_archive is this same page pinned to 'all'.
    """
    today = date.today()
    if request.GET.get('period') in ('month', 'all'):
        period = request.GET['period']

    try:
        year = int(request.GET.get('year', today.year))
    except (TypeError, ValueError):
        year = today.year
    try:
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        month = today.month
    if not 1 <= month <= 12:
        month = today.month

    # product is joined too: each row says whether the listing behind it
    # still exists, which would otherwise be a query per sale.
    sales = Sale.objects.select_related('sold_by', 'product')
    if period == 'month':
        sales = sales.filter(sold_at__year=year, sold_at__month=month)

    search_query = (request.GET.get('search') or '').strip()
    if search_query:
        sales = sales.filter(
            Q(product_name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(category_name__icontains=search_query) |
            Q(catalog_code__icontains=search_query)
        )

    totals = sales.aggregate(total_revenue=Sum('price'), total_count=Count('id'))

    # The trailing order_by is what keeps these grouped by one column: it
    # clears Sale's default '-sold_at' ordering, which would otherwise join
    # the GROUP BY and split every category across its individual sale dates.
    by_category = sales.values('category_name').annotate(
        total=Sum('price'), count=Count('id')
    ).order_by('-total')

    by_brand = sales.values('brand').annotate(
        total=Sum('price'), count=Count('id')
    ).order_by('-total')

    # Years to offer in the filter: every year that has at least one sale,
    # plus the current year so the dropdown is never empty on a fresh store.
    sale_years = set(Sale.objects.dates('sold_at', 'year').values_list('sold_at__year', flat=True))
    sale_years.add(today.year)
    available_years = sorted(sale_years, reverse=True)

    months = sorted(MONTHS.items())

    context = {
        'period': period,
        'sales': sales,
        'total_revenue': totals['total_revenue'] or 0,
        'total_count': totals['total_count'] or 0,
        'by_category': by_category,
        'by_brand': by_brand,
        'selected_year': year,
        'selected_month': month,
        'available_years': available_years,
        'months': months,
        'search_query': search_query,
        'active': 'sales',
    }
    return render(request, 'shop/product/sales_report.html', context)


def sales_archive(request):
    """
    The all-time view of the sales page above, kept on its own URL: it is a
    distinct place to navigate to from the sidebar, and links made to
    /management/archive/ before the two pages merged still land on it.
    """
    return sales_report(request, period='all')


# ==========================================
# 🏠 HOMEPAGE SECTIONS CONTROLLER
# ==========================================

@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def manage_homepage(request):
    """
    Lets staff/managers write the two editorial bands on the homepage: the
    promise sitting between the hero slideshow and the category rows, and
    the closing invitation between those rows and the footer.

    Everything between the two — the hero slides and the "Newest In" rows —
    is built from the catalog itself and is switched on per category from
    the Categories page, so there is nothing to write for it here.
    """
    content_obj = HomePageContent.get_solo()

    if request.method == 'POST':
        form = HomePageContentForm(request.POST, instance=content_obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Homepage sections updated!"))
            return _panel_response(request, redirect('shop:manage_homepage'))
        else:
            messages.error(request, _("Please correct the entry errors below."))
            if _wants_json(request):
                return _panel_response(request, None, ok=False, errors=_form_errors(form))
    else:
        form = HomePageContentForm(instance=content_obj)

    # One row per language, each holding that language's variant of every
    # field in a fixed order the template loops over — the same shape as
    # manage_about, so the template renders one block per language instead
    # of tripling the markup for English/Russian/Kyrgyz by hand.
    homepage_lang_fields = [
        (
            lang,
            form[f'site_name{suffix}'],
            form[f'promise_heading{suffix}'], form[f'promise_card_heading{suffix}'],
            form[f'promise_text{suffix}'], form[f'promise_button_text{suffix}'],
            form[f'promise_stat_label{suffix}'], form[f'promise_stat_caption{suffix}'],
            form[f'invite_eyebrow{suffix}'], form[f'invite_heading{suffix}'],
            form[f'invite_text{suffix}'], form[f'invite_button_text{suffix}'],
        )
        for lang, suffix in [('en', ''), ('ru', '_ru'), ('ky', '_ky')]
    ]

    context = {
        'form': form,
        'homepage_lang_fields': homepage_lang_fields,
        # Shown beside the stock-count fields so the admin can see what the
        # number they are labelling currently reads on the live page.
        'in_stock_count': Product.objects.filter(is_sold=False).count(),
        'active': 'homepage',
    }
    return render(request, 'shop/product/homepage_settings.html', context)


# ==========================================
# 🗑️ REMOVED LISTINGS CONTROLLER
# ==========================================

@login_required
@user_passes_test(is_admin_or_manager, login_url='shop:product_list', redirect_field_name=None)
def removed_products(request):
    """
    Every listing taken off the catalog, newest removal first, with restore
    and permanent delete on each.

    This is the only place removed listings appear in the panel: the
    Products page shows what is on sale and nothing else, so undoing a
    removal — whether it happened a moment or weeks ago — starts here.
    """
    removed = Product.all_objects.filter(
        deleted_at__isnull=False
    ).select_related('category').order_by('-deleted_at')

    search_query = (request.GET.get('search') or '').strip()
    if search_query:
        # Same lookup as the catalog search on the Products page: the catalog
        # number is how staff identify a specific listing, with name/brand as
        # the more casual fallback.
        search_filter = (
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )
        if search_query.lstrip('#').isdigit():
            search_filter |= Q(category_number=int(search_query.lstrip('#')))
        removed = removed.filter(search_filter)

    removed = _annotate_removal_kind(removed)

    context = {
        'removed_products': removed,
        'search_query': search_query,
        # Counted off the list actually shown, so the tallies agree with it
        # while a search is narrowing things down. The sidebar badge
        # (removed_count, from the management_nav processor) stays the
        # unfiltered total on purpose.
        'shown_count': len(removed),
        'sold_count': sum(1 for product in removed if product.was_sold),
        'deleted_count': sum(1 for product in removed if not product.was_sold),
        'active': 'removed',
    }
    return render(request, 'shop/product/removed_products.html', context)
