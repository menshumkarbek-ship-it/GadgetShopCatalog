from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from .models import (
    Category, Product, ProductImage, ContactSettings, AboutPageContent, HomePageContent, Sale,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'order')


# Admin styling for Products
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'price', 'is_sold', 'created_at')
    list_filter = ('is_sold', 'category', 'brand') # Let admin filter sold/unsold quickly
    search_fields = ('name', 'brand', 'description')
    prepopulated_fields = {'slug': ('name',)} # Automatically generates slugs as you type names
    inlines = [ProductImageInline]

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_featured_in_hero', 'show_newest_row')
    list_editable = ('is_featured_in_hero', 'show_newest_row')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ContactSettings)
class ContactSettingsAdmin(admin.ModelAdmin):
    """
    Singleton editor: the store only ever has one set of contact channels
    (email, phone, WhatsApp, Telegram, Instagram), shown on the Contact page
    and used to prefill "ask about this product" messages.
    """
    fields = ('email', 'phone_number', 'whatsapp_number', 'telegram_username', 'instagram_username')

    def has_add_permission(self, request):
        # Block adding a second row once the singleton exists.
        return not ContactSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Skip the list page entirely and jump straight to the single
        # instance's edit form (creating it on first visit if needed).
        obj = ContactSettings.get_solo()
        return redirect(reverse('admin:shop_contactsettings_change', args=[obj.pk]))


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'brand', 'category_name', 'price', 'sold_at', 'sold_by')
    list_filter = ('category_name', 'brand', 'sold_at')
    search_fields = ('product_name', 'brand', 'catalog_code')
    date_hierarchy = 'sold_at'

    def has_add_permission(self, request):
        # Sales are only ever created automatically when a product is
        # removed from the catalog, never entered by hand.
        return False


@admin.register(AboutPageContent)
class AboutPageContentAdmin(admin.ModelAdmin):
    """
    Singleton editor: the store only ever has one "About Us" page, so this
    edits that single row directly rather than showing a list.
    """
    fields = (
        'badge_text', 'heading', 'intro_text',
        'visit_heading', 'visit_text', 'store_address_line1', 'store_address_line2', 'store_image',
        'cta_heading', 'cta_text',
    )

    def has_add_permission(self, request):
        return not AboutPageContent.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = AboutPageContent.get_solo()
        return redirect(reverse('admin:shop_aboutpagecontent_change', args=[obj.pk]))


@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    """
    Singleton editor for the homepage's two editorial bands. The in-app
    management panel is where staff normally edit these; this exists so the
    row is reachable from Django admin like the other content singletons.
    """

    def has_add_permission(self, request):
        return not HomePageContent.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = HomePageContent.get_solo()
        return redirect(reverse('admin:shop_homepagecontent_change', args=[obj.pk]))
