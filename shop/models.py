import logging

from django.conf import settings
from django.db import models
from .utils import process_no_bg_image, translatable_property

logger = logging.getLogger(__name__)


# ==========================================
# 🏷️ CATEGORY MANAGEMENT
# ==========================================

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_featured_in_hero = models.BooleanField(
        default=False,
        help_text="Show this category's newest in-stock product as an auto-rotating homepage announcement slide."
    )
    show_newest_row = models.BooleanField(
        default=True,
        help_text="Show this category's own \"Newest In\" slideshow row on the homepage."
    )

    # Per-language name overrides: `name` above is the default/fallback.
    # Leave either blank to fall back to `name` for that language. The slug
    # (used in URLs) is intentionally NOT translated.
    name_ru = models.CharField(max_length=100, blank=True, verbose_name="Name (Russian)")
    name_ky = models.CharField(max_length=100, blank=True, verbose_name="Name (Kyrgyz)")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    translated_name = translatable_property('name')


# ==========================================
# ☎️ CONTACT SETTINGS (SINGLETON)
# ==========================================

class ContactSettings(models.Model):
    """
    Store-wide contact channels, editable by the admin from Django admin.
    Only one row ever exists (enforced via save()); the shop.contact_settings
    context processor exposes it to every template as `contact_settings`.
    """
    email = models.EmailField(
        blank=True,
        help_text="Public support email shown on the Contact page."
    )
    phone_number = models.CharField(
        max_length=32, blank=True,
        help_text="Phone number for calls/SMS, e.g. +996700123456"
    )
    whatsapp_number = models.CharField(
        max_length=32, blank=True,
        help_text="WhatsApp number with country code, digits only, e.g. 996700123456"
    )
    telegram_username = models.CharField(
        max_length=100, blank=True,
        help_text="Telegram username without the @, e.g. techvault_support"
    )
    instagram_username = models.CharField(
        max_length=100, blank=True,
        help_text="Instagram username without the @, e.g. techvault.shop"
    )

    class Meta:
        verbose_name = "Contact Settings"
        verbose_name_plural = "Contact Settings"

    def __str__(self):
        return "Contact Settings"

    def save(self, *args, **kwargs):
        # Enforce a single row: this table only ever holds the store's one
        # shared set of contact channels.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Never allow deleting the singleton row from anywhere in the app.
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def whatsapp_digits(self):
        return ''.join(ch for ch in self.whatsapp_number if ch.isdigit())

    @property
    def phone_digits(self):
        digits = ''.join(ch for ch in self.phone_number if ch.isdigit() or ch == '+')
        return digits

    @property
    def telegram_handle(self):
        return self.telegram_username.lstrip('@').strip()

    @property
    def instagram_handle(self):
        return self.instagram_username.lstrip('@').strip()

    @property
    def has_any_channel(self):
        """
        Whether a customer can actually reach the store. Product pages hide
        their "Enquire" button when this is False, so nobody is sent to a
        Contact page that has nothing on it.
        """
        return any([
            self.email,
            self.phone_digits,
            self.whatsapp_digits,
            self.telegram_handle,
            self.instagram_handle,
        ])


# ==========================================
# 📖 ABOUT PAGE CONTENT (SINGLETON)
# ==========================================

class AboutPageContent(models.Model):
    """
    Store-wide site identity and "About Us" page copy, editable by the admin
    from the in-app management panel. Singleton like ContactSettings: only
    one row ever exists (enforced via save()).
    """
    badge_text = models.CharField(
        max_length=100, blank=True, default="Enterprise Architecture",
        help_text="Small pill label above the page heading, e.g. 'Family Owned Since 2010'."
    )
    heading = models.CharField(max_length=150, default="About TechVault")
    intro_text = models.TextField(
        default=(
            "TechVault is an online showcase for the phones, laptops, and tablets we carry. "
            "Browse the full catalog, compare specifications, and find your next device before you visit us."
        ),
        help_text="The main story paragraph under the heading. Write about your shop, your market, and what makes you different."
    )

    visit_heading = models.CharField(max_length=150, blank=True, default="See It In Person")
    visit_text = models.TextField(
        blank=True,
        default=(
            "This catalog is for browsing: use it to compare specifications and shortlist the devices you like, "
            "then stop by our store to see them up close and speak with our team."
        )
    )
    store_address_line1 = models.CharField(max_length=200, blank=True, default="100 Tech Vault Plaza, Suite 404")
    store_address_line2 = models.CharField(max_length=200, blank=True, default="Silicon District, CA 94016")
    store_image = models.ImageField(
        upload_to='about/', blank=True, null=True,
        help_text="Optional photo of your storefront. Falls back to a generic map graphic if left empty."
    )
    # The rest of the Visit Us section: the two things a customer checks
    # before setting off.
    opening_hours = models.TextField(
        blank=True,
        help_text="One line per range, e.g. 'Mon–Sat 10:00–20:00' then 'Sun 11:00–18:00'. Leave blank to hide."
    )
    map_url = models.URLField(
        max_length=500, blank=True,
        help_text="Link to the store on Google Maps or 2GIS. Powers the Directions button; leave blank to hide it."
    )

    cta_heading = models.CharField(max_length=150, blank=True, default="Ready to Find Your Next Device?")
    cta_text = models.TextField(
        blank=True,
        default="Browse our full catalog of phones, laptops, and tablets, then visit us in-store or get in touch to learn more."
    )

    # Per-language overrides for every field above. Each defaults to blank
    # and falls back to the base (English) field when empty, so filling
    # these in is entirely optional per language.
    badge_text_ru = models.CharField(max_length=100, blank=True, verbose_name="Badge Text (Russian)")
    badge_text_ky = models.CharField(max_length=100, blank=True, verbose_name="Badge Text (Kyrgyz)")
    heading_ru = models.CharField(max_length=150, blank=True, verbose_name="Page Heading (Russian)")
    heading_ky = models.CharField(max_length=150, blank=True, verbose_name="Page Heading (Kyrgyz)")
    intro_text_ru = models.TextField(blank=True, verbose_name="Your Story (Russian)")
    intro_text_ky = models.TextField(blank=True, verbose_name="Your Story (Kyrgyz)")
    visit_heading_ru = models.CharField(max_length=150, blank=True, verbose_name="Visit Section Heading (Russian)")
    visit_heading_ky = models.CharField(max_length=150, blank=True, verbose_name="Visit Section Heading (Kyrgyz)")
    visit_text_ru = models.TextField(blank=True, verbose_name="Visit Section Text (Russian)")
    visit_text_ky = models.TextField(blank=True, verbose_name="Visit Section Text (Kyrgyz)")
    store_address_line1_ru = models.CharField(max_length=200, blank=True, verbose_name="Address Line 1 (Russian)")
    store_address_line1_ky = models.CharField(max_length=200, blank=True, verbose_name="Address Line 1 (Kyrgyz)")
    store_address_line2_ru = models.CharField(max_length=200, blank=True, verbose_name="Address Line 2 (Russian)")
    store_address_line2_ky = models.CharField(max_length=200, blank=True, verbose_name="Address Line 2 (Kyrgyz)")
    opening_hours_ru = models.TextField(blank=True, verbose_name="Opening Hours (Russian)")
    opening_hours_ky = models.TextField(blank=True, verbose_name="Opening Hours (Kyrgyz)")
    cta_heading_ru = models.CharField(max_length=150, blank=True, verbose_name="Banner Heading (Russian)")
    cta_heading_ky = models.CharField(max_length=150, blank=True, verbose_name="Banner Heading (Kyrgyz)")
    cta_text_ru = models.TextField(blank=True, verbose_name="Banner Text (Russian)")
    cta_text_ky = models.TextField(blank=True, verbose_name="Banner Text (Kyrgyz)")

    class Meta:
        verbose_name = "About Page Content"
        verbose_name_plural = "About Page Content"

    def __str__(self):
        return "About Page Content"

    def save(self, *args, **kwargs):
        # Enforce a single row: the About page only ever has one shared copy.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Never allow deleting the singleton row from anywhere in the app.
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    translated_badge_text = translatable_property('badge_text')
    translated_heading = translatable_property('heading')
    translated_intro_text = translatable_property('intro_text')
    translated_visit_heading = translatable_property('visit_heading')
    translated_visit_text = translatable_property('visit_text')
    translated_store_address_line1 = translatable_property('store_address_line1')
    translated_store_address_line2 = translatable_property('store_address_line2')
    translated_opening_hours = translatable_property('opening_hours')
    translated_cta_heading = translatable_property('cta_heading')
    translated_cta_text = translatable_property('cta_text')


# ==========================================
# 🏠 HOME PAGE CONTENT (SINGLETON)
# ==========================================

class HomePageContent(models.Model):
    """
    The copy in the two editorial bands on the homepage: the "why shop here"
    promise sitting between the hero slideshow and the category rows, and the
    "we'll order it in" invitation closing the page above the footer.

    Everything between those two bands — the hero slides and the "Newest In"
    rows — is generated from the catalog itself, so there is nothing to write
    here for it; those are switched on per category from the Categories page.

    Singleton like ContactSettings and AboutPageContent: only one row ever
    exists (enforced via save()). The Russian and Kyrgyz defaults below are
    the translations these strings already shipped with while they were
    hardcoded template text, so handing them to the admin doesn't leave
    either language suddenly reading English.
    """

    # --- The store's name: navbar, browser tab, footer, link previews ---
    # Edited with the homepage because that is where a visitor first meets
    # it, though it is shown on every page.
    site_name = models.CharField(
        max_length=60, default="TechVault",
        help_text="The store/market name shown in the navbar, browser tab, and footer across the whole site."
    )
    site_name_ru = models.CharField(max_length=60, blank=True, verbose_name="Store / Market Name (Russian)")
    site_name_ky = models.CharField(max_length=60, blank=True, verbose_name="Store / Market Name (Kyrgyz)")

    # --- Band 1: the promise, between the hero and the category rows ---
    promise_heading = models.CharField(
        max_length=150, blank=True, default="Why shop here",
        help_text="Small heading above the promise card."
    )
    promise_card_heading = models.CharField(
        max_length=200, blank=True, default="Checked devices at the price on the tag"
    )
    promise_text = models.TextField(
        blank=True,
        default=(
            "Everything listed is on our shelves right now. We test and photograph each "
            "device ourselves, and the price on the page is the price at the counter."
        )
    )
    promise_button_text = models.CharField(
        max_length=80, blank=True, default="Browse the catalog",
        help_text="Label on the button linking to the catalog. Leave blank to hide the button."
    )
    promise_stat_label = models.CharField(
        max_length=100, blank=True, default="devices in stock",
        help_text="Caption under the live in-stock count. The number itself is counted from the catalog and isn't editable."
    )
    promise_stat_caption = models.CharField(
        max_length=100, blank=True, default="Restocked every week",
        help_text="Smaller line under the stock count, e.g. how often you restock."
    )

    # --- Band 2: the invitation, between the category rows and the footer ---
    invite_eyebrow = models.CharField(
        max_length=100, blank=True, default="Looking for something else",
        help_text="Small coloured line above the closing heading."
    )
    invite_heading = models.CharField(
        max_length=200, blank=True, default="Not in the catalog? We will bring it in"
    )
    invite_text = models.TextField(
        blank=True,
        default=(
            "The shelves change every week. Tell us which model you are after and we will "
            "order it in or let you know the moment it arrives."
        )
    )
    invite_button_text = models.CharField(
        max_length=80, blank=True, default="Tell us what you need",
        help_text="Label on the button linking to the Contact page. Hidden automatically while no contact channel is configured."
    )

    # Per-language overrides. Unlike the other content singletons these ship
    # pre-filled rather than blank — see the class docstring. Clearing one
    # falls back to the base (English) field, exactly as elsewhere.
    promise_heading_ru = models.CharField(max_length=150, blank=True, default="Почему у нас", verbose_name="Section Heading (Russian)")
    promise_heading_ky = models.CharField(max_length=150, blank=True, default="Эмне үчүн бизде", verbose_name="Section Heading (Kyrgyz)")
    promise_card_heading_ru = models.CharField(max_length=200, blank=True, default="Проверенная техника по честной цене", verbose_name="Card Heading (Russian)")
    promise_card_heading_ky = models.CharField(max_length=200, blank=True, default="Текшерилген техника адилет баада", verbose_name="Card Heading (Kyrgyz)")
    promise_text_ru = models.TextField(
        blank=True, verbose_name="Card Text (Russian)",
        default=(
            "Всё, что в каталоге, сейчас стоит у нас на полке. Каждое устройство мы "
            "проверяем и фотографируем сами, а цена на странице совпадает с ценой на кассе."
        )
    )
    promise_text_ky = models.TextField(
        blank=True, verbose_name="Card Text (Kyrgyz)",
        default=(
            "Каталогдогунун баары ушул учурда бизде текчеде турат. Ар бир түзмөктү өзүбүз "
            "текшерип, сүрөткө тартабыз, ал эми барактагы баа кассадагы баа менен бирдей."
        )
    )
    promise_button_text_ru = models.CharField(max_length=80, blank=True, default="Смотреть каталог", verbose_name="Button Label (Russian)")
    promise_button_text_ky = models.CharField(max_length=80, blank=True, default="Каталогду көрүү", verbose_name="Button Label (Kyrgyz)")
    promise_stat_label_ru = models.CharField(max_length=100, blank=True, default="устройств в наличии", verbose_name="Stock Count Label (Russian)")
    promise_stat_label_ky = models.CharField(max_length=100, blank=True, default="түзмөк кампада бар", verbose_name="Stock Count Label (Kyrgyz)")
    promise_stat_caption_ru = models.CharField(max_length=100, blank=True, default="Пополняем каждую неделю", verbose_name="Stock Count Caption (Russian)")
    promise_stat_caption_ky = models.CharField(max_length=100, blank=True, default="Жума сайын толукталат", verbose_name="Stock Count Caption (Kyrgyz)")

    invite_eyebrow_ru = models.CharField(max_length=100, blank=True, default="Ищете другое", verbose_name="Eyebrow (Russian)")
    invite_eyebrow_ky = models.CharField(max_length=100, blank=True, default="Башка нерсе издеп жатасызбы", verbose_name="Eyebrow (Kyrgyz)")
    invite_heading_ru = models.CharField(max_length=200, blank=True, default="Нет в каталоге? Привезём под заказ", verbose_name="Heading (Russian)")
    invite_heading_ky = models.CharField(max_length=200, blank=True, default="Каталогдо жокпу? Алып келебиз", verbose_name="Heading (Kyrgyz)")
    invite_text_ru = models.TextField(
        blank=True, verbose_name="Text (Russian)",
        default=(
            "Полки меняются каждую неделю. Скажите, какая модель нужна, — закажем или "
            "сообщим, как только она появится."
        )
    )
    invite_text_ky = models.TextField(
        blank=True, verbose_name="Text (Kyrgyz)",
        default=(
            "Текчелер жума сайын жаңырат. Кайсы модель керек экенин айтыңыз — заказ "
            "кылабыз же келери менен кабарлайбыз."
        )
    )
    invite_button_text_ru = models.CharField(max_length=80, blank=True, default="Расскажите, что нужно", verbose_name="Button Label (Russian)")
    invite_button_text_ky = models.CharField(max_length=80, blank=True, default="Эмне керек экенин айтыңыз", verbose_name="Button Label (Kyrgyz)")

    class Meta:
        verbose_name = "Home Page Content"
        verbose_name_plural = "Home Page Content"

    def __str__(self):
        return "Home Page Content"

    def save(self, *args, **kwargs):
        # Enforce a single row: the homepage only ever has one set of bands.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Never allow deleting the singleton row from anywhere in the app.
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    translated_site_name = translatable_property('site_name')
    translated_promise_heading = translatable_property('promise_heading')
    translated_promise_card_heading = translatable_property('promise_card_heading')
    translated_promise_text = translatable_property('promise_text')
    translated_promise_button_text = translatable_property('promise_button_text')
    translated_promise_stat_label = translatable_property('promise_stat_label')
    translated_promise_stat_caption = translatable_property('promise_stat_caption')
    translated_invite_eyebrow = translatable_property('invite_eyebrow')
    translated_invite_heading = translatable_property('invite_heading')
    translated_invite_text = translatable_property('invite_text')
    translated_invite_button_text = translatable_property('invite_button_text')


# ==========================================
# 📱 PRODUCT CATALOG & AUTOMATED NO-BG PROCESSOR
# ==========================================

class AvailableProductManager(models.Manager):
    """
    Default manager: hides listings that staff removed from the catalog.

    Removal is a soft delete (see Product.deleted_at), so filtering here
    rather than at each call site means a forgotten `.filter()` can never
    leak a removed product back onto the storefront. Use
    `Product.all_objects` for the places that must still see them —
    uniqueness checks, the sales history, and the restore flow.
    """

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.CharField(max_length=100, db_index=True, help_text="e.g., Apple, Samsung, Asus")
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    description = models.TextField()
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    # Per-language overrides for name/description. `name`/`description` above
    # are the default/fallback; leave either blank to fall back for that
    # language. Brand, price, and slug are intentionally not translated.
    name_ru = models.CharField(max_length=255, blank=True, verbose_name="Product Title (Russian)")
    name_ky = models.CharField(max_length=255, blank=True, verbose_name="Product Title (Kyrgyz)")
    description_ru = models.TextField(blank=True, verbose_name="Product Description (Russian)")
    description_ky = models.TextField(blank=True, verbose_name="Product Description (Kyrgyz)")

    # A short, stable, per-category catalog number (0, 1, 2, ...), assigned
    # once when the product is first created and never changed afterward.
    # Shown to customers on product cards, and lets an admin quickly find and
    # delete the exact listing once it's sold, by searching for its number
    # instead of scrolling through the whole catalog.
    category_number = models.PositiveIntegerField(default=0, db_index=True)

    specifications = models.JSONField(
        default=dict,
        help_text="Store characteristics as JSON. (e.g., {'RAM': '16GB', 'Storage': '512GB'})"
    )

    is_sold = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Set when staff removes the listing from the catalog. The row (and its
    # photos) are kept so a mis-click is recoverable — there is no shell
    # access on the deployed host to undo a real delete.
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = AvailableProductManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']
        # Related lookups (Sale.product) and the admin must resolve removed
        # rows too, so they go through the unfiltered manager.
        base_manager_name = 'all_objects'
        indexes = [
            models.Index(fields=['is_sold', 'brand']),
            models.Index(fields=['is_sold', '-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['category', 'category_number'], name='unique_category_number_per_category'),
        ]

    def __str__(self):
        status = "SOLD" if self.is_sold else "AVAILABLE"
        return f"[{status}] {self.brand} - {self.name} (#{self.category_number})"

    @property
    def catalog_code(self):
        """Short, human-friendly, searchable code shown on cards, e.g. 'PHONES-3'."""
        prefix = ''.join(ch for ch in self.category.name.upper() if ch.isalnum())[:6] or 'ITEM'
        return f"{prefix}-{self.category_number}"

    translated_name = translatable_property('name')
    translated_description = translatable_property('description')

    def save(self, *args, **kwargs):
        if self.pk is None and self.category_id:
            # all_objects, not objects: a removed listing keeps its number,
            # and reusing it would trip unique_category_number_per_category.
            last_number = Product.all_objects.filter(category_id=self.category_id).aggregate(
                models.Max('category_number')
            )['category_number__max']
            self.category_number = 0 if last_number is None else last_number + 1

        if self.image and hasattr(self.image, 'file'):
            try:
                filename, content = process_no_bg_image(self.image, self.slug if self.slug else 'device')
                self.image.save(filename, content, save=False)
            except Exception:
                # The upload is still usable unprocessed, so don't fail the
                # save — but this must be visible, not printed into the void.
                logger.exception('Background removal failed for product image %r', self.slug)

        super().save(*args, **kwargs)


# ==========================================
# 🖼️ PRODUCT GALLERY (ADDITIONAL PHOTOS)
# ==========================================

class ProductImage(models.Model):
    """
    Extra photos for a product, beyond the single primary `Product.image`.
    Admins can upload several images per product from the management panel;
    each gets the same background-removal treatment as the primary photo so
    the whole gallery looks consistent.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='products/gallery/')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Photo for {self.product.name} (#{self.pk})"

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image, 'file'):
            try:
                prefix = f"{self.product.slug if self.product_id else 'device'}-gallery-{self.pk or 'new'}"
                filename, content = process_no_bg_image(self.image, prefix)
                self.image.save(filename, content, save=False)
            except Exception:
                logger.exception('Background removal failed for gallery photo of product %s', self.product_id)

        super().save(*args, **kwargs)


# ==========================================
# 💰 SALES RECORD (for monthly sales reporting)
# ==========================================

class Sale(models.Model):
    """
    A snapshot of one product leaving the catalog as sold, created the
    moment staff removes it from "Manage Webpage" (shop.views.delete_product).
    Fields are copied from the product at that moment (not looked up live)
    so that later edits or deletion of the product never change a past
    month's sales report.
    """
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales',
        help_text="The catalog listing this sale came from, if it still exists."
    )
    product_name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, blank=True)
    category_name = models.CharField(max_length=100, blank=True)
    catalog_code = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at the moment of the sale.")
    sold_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_sales'
    )

    class Meta:
        ordering = ['-sold_at']
        indexes = [
            models.Index(fields=['sold_at']),
        ]

    def __str__(self):
        return f"{self.product_name} — {self.price} ({self.sold_at:%Y-%m-%d})"
