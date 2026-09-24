import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User, Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation

from .models import AboutPageContent, Category, ContactSettings, HomePageContent, Product, Sale


class StorefrontTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Phones', slug='phones')

    def make_product(self, name, slug, price):
        return Product.objects.create(
            category=self.category,
            brand='Example',
            name=name,
            slug=slug,
            price=Decimal(price),
            description='A tested product.',
        )

    def test_specs_page_renders(self):
        product = self.make_product('Phone', 'phone', '100.00')
        response = self.client.get(reverse('shop:product_specs', args=[product.slug]))
        self.assertEqual(response.status_code, 200)

    def test_product_detail_page_has_no_cart_action(self):
        product = self.make_product('Phone', 'phone', '100.00')
        response = self.client.get(reverse('shop:product_detail', args=[product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Add to Cart')
        self.assertNotContains(response, '/cart/add/')

    def test_homepage_hero_slide_uses_newest_product_in_featured_category(self):
        self.category.is_featured_in_hero = True
        self.category.save(update_fields=['is_featured_in_hero'])
        self.make_product('Older Phone', 'older-phone', '400.00')
        newest_phone = self.make_product('Newest Phone', 'newest-phone', '500.00')

        response = self.client.get(reverse('shop:home'))

        self.assertEqual(len(response.context['hero_slides']), 1)
        self.assertEqual(response.context['hero_slides'][0]['product'], newest_phone)

    def test_catalog_shows_all_products_without_a_filter(self):
        for i in range(5):
            self.make_product(f'Phone {i}', f'phone-{i}', '100.00')

        response = self.client.get(reverse('shop:product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_active_filters'])
        self.assertEqual(len(response.context['products']), 5)

    def test_catalog_filter_narrows_results_but_keeps_pagination(self):
        self.make_product('Matching Phone', 'matching-phone', '100.00')
        other_category = Category.objects.create(name='Tablets', slug='tablets')
        Product.objects.create(
            category=other_category,
            brand='Example',
            name='Other Tablet',
            slug='other-tablet',
            price=Decimal('200.00'),
            description='A tested tablet.',
        )

        response = self.client.get(reverse('shop:product_list'), {'type': 'phones'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_active_filters'])
        self.assertEqual(len(response.context['products']), 1)

    def test_anonymous_visitor_sees_no_settings_link(self):
        response = self.client.get(reverse('shop:home'))

        self.assertNotContains(response, reverse('shop:management_home'))

    def test_sign_in_page_wears_the_storefront_theme_and_still_signs_in(self):
        User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        response = self.client.get(reverse('admin:login'))

        self.assertContains(response, 'id="globalnav"')
        self.assertContains(response, 'btn btn-blue')
        self.assertContains(response, 'noindex, nofollow')
        self.assertNotContains(response, 'bg-slate-950')

        wrong = self.client.post(reverse('admin:login'), {'username': 'manager', 'password': 'nope'})
        self.assertContains(wrong, 'fa-triangle-exclamation')

        right = self.client.post(reverse('admin:login'), {
            'username': 'manager', 'password': 'manager-password-123', 'next': reverse('shop:create_product'),
        })
        self.assertRedirects(right, reverse('shop:create_product'))

    def test_staff_sees_settings_link_and_sign_out_lives_inside_it(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        home = self.client.get(reverse('shop:home'))
        # Settings opens the panel's front door — on a phone that is the
        # section list — rather than dropping the admin into one section.
        self.assertContains(home, reverse('shop:management_home'))
        # Sign Out moved off the navbar into the Settings hub.
        self.assertNotContains(home, reverse('admin:logout'))

        hub = self.client.get(reverse('shop:management_home'))
        self.assertContains(hub, reverse('admin:logout'))

    def test_manager_group_member_can_reach_add_product_page(self):
        manager = User.objects.create_user(username='group-manager', password='manager-password-123')
        manager.groups.add(Group.objects.create(name='Managers'))
        self.client.force_login(manager)

        response = self.client.get(reverse('shop:create_product'))

        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_reach_add_product_page(self):
        user = User.objects.create_user(username='buyer', password='safe-password-123')
        self.client.force_login(user)

        response = self.client.get(reverse('shop:create_product'))

        self.assertRedirects(response, reverse('shop:product_list'))

    def test_add_product_form_offers_brand_suggestions_but_stays_free_text(self):
        self.make_product('Phone', 'phone', '100.00')
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse('shop:create_product'), {'action': 'new'})

        self.assertContains(response, 'id="brand-suggestions"')
        self.assertContains(response, 'value="Example"')
        self.assertContains(response, 'list="brand-suggestions"')

    def test_staff_can_create_a_new_category(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        response = self.client.post(reverse('shop:create_category'), {'name': 'Headphones', 'slug': ''}, follow=True)

        self.assertEqual(response.status_code, 200)
        category = Category.objects.get(name='Headphones')
        self.assertEqual(category.slug, 'headphones')

    def test_regular_user_cannot_create_a_category(self):
        user = User.objects.create_user(username='buyer', password='safe-password-123')
        self.client.force_login(user)

        response = self.client.get(reverse('shop:create_category'))

        self.assertRedirects(response, reverse('shop:product_list'))

    def test_cyrillic_category_name_gets_a_non_empty_transliterated_slug(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        self.client.post(reverse('shop:create_category'), {'name': 'Наушники', 'slug': ''})

        category = Category.objects.get(name='Наушники')
        self.assertEqual(category.slug, 'naushniki')
        # The homepage must be able to link to it without raising NoReverseMatch.
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)

    def test_cyrillic_product_name_gets_a_non_empty_transliterated_slug(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        self.client.post(reverse('shop:create_product'), {
            'category': self.category.id,
            'brand': 'Sony',
            'name': 'Наушники Про',
            'price': '199.99',
            'description': 'Test description.',
            'slug': '',
        })

        product = Product.objects.get(name='Наушники Про')
        self.assertTrue(product.slug)
        self.assertNotEqual(product.slug, '')

    def test_toggling_category_adds_and_removes_hero_slide(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        self.make_product('Phone', 'phone', '100.00')

        self.assertEqual(self.category.is_featured_in_hero, False)
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.context['hero_slides'], [])

        self.client.post(reverse('shop:toggle_category_hero', args=[self.category.id]))
        self.category.refresh_from_db()
        self.assertTrue(self.category.is_featured_in_hero)

        response = self.client.get(reverse('shop:home'))
        self.assertEqual(len(response.context['hero_slides']), 1)
        self.assertEqual(response.context['hero_slides'][0]['category'], self.category)

        self.client.post(reverse('shop:toggle_category_hero', args=[self.category.id]))
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.context['hero_slides'], [])

    def test_new_category_can_be_created_already_featured_in_hero(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        self.client.post(reverse('shop:create_category'), {
            'name': 'Powerbanks', 'slug': '', 'is_featured_in_hero': 'on',
        })

        category = Category.objects.get(name='Powerbanks')
        self.assertTrue(category.is_featured_in_hero)

    def test_regular_user_cannot_toggle_hero_slide(self):
        user = User.objects.create_user(username='buyer', password='safe-password-123')
        self.client.force_login(user)

        response = self.client.post(reverse('shop:toggle_category_hero', args=[self.category.id]))

        self.assertRedirects(response, reverse('shop:product_list'))
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_featured_in_hero)

    def test_marking_a_product_sold_hides_it_but_keeps_the_row_and_records_a_sale(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')

        self.client.post(reverse('shop:sell_product', args=[product.id]))

        # Gone from the storefront...
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertEqual(self.client.get(reverse('shop:product_detail', args=['phone'])).status_code, 404)
        # ...but the row survives, so the removal is recoverable.
        product.refresh_from_db()
        self.assertIsNotNone(product.deleted_at)

        sale = Sale.objects.get(product=product)
        self.assertEqual(sale.price, Decimal('250.00'))
        self.assertEqual(sale.product_name, 'Phone')

    def test_restoring_a_product_puts_it_back_and_drops_the_recorded_sale(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))

        self.client.post(reverse('shop:restore_product', args=[product.id]))

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertEqual(self.client.get(reverse('shop:product_detail', args=['phone'])).status_code, 200)
        # The sale it recorded must go too, or the month's report stays inflated.
        self.assertEqual(Sale.objects.filter(product=product).count(), 0)

    def test_deleting_a_product_hides_it_without_recording_a_sale(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Added by mistake', 'mistake', '250.00')

        self.client.post(reverse('shop:remove_product', args=[product.id]))

        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        product.refresh_from_db()
        self.assertIsNotNone(product.deleted_at)
        self.assertFalse(Sale.objects.exists())

        # The Removed page says which kind of removal it was.
        response = self.client.get(reverse('shop:removed_products'))
        removed = {p.pk: p for p in response.context['removed_products']}
        self.assertFalse(removed[product.pk].was_sold)

        # The Products page is only for listings on sale.
        response = self.client.get(reverse('shop:create_product'))
        self.assertNotIn('removed_products', response.context)
        self.assertNotContains(response, 'Added by mistake')

    def test_restoring_a_deleted_product_leaves_earlier_sales_alone(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        # A genuine sale of a different unit, recorded some time ago.
        earlier = Sale.objects.create(
            product=product, product_name='Phone', brand='Brand', category_name='Phones',
            catalog_code='PHONE-1', price=Decimal('250.00'), sold_by=staff,
        )
        Sale.objects.filter(pk=earlier.pk).update(sold_at=timezone.now() - timedelta(days=3))

        self.client.post(reverse('shop:remove_product', args=[product.id]))
        self.client.post(reverse('shop:restore_product', args=[product.id]))

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertTrue(Sale.objects.filter(pk=earlier.pk).exists())

    def test_staff_can_strike_a_mistaken_sale_from_the_report(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        sale = Sale.objects.get(product=product)

        response = self.client.post(
            reverse('shop:discard_sale', args=[sale.id]),
            {'month': sale.sold_at.month, 'year': sale.sold_at.year},
        )

        self.assertRedirects(
            response, f"{reverse('shop:sales_report')}?month={sale.sold_at.month}&year={sale.sold_at.year}",
        )
        self.assertFalse(Sale.objects.exists())
        # Striking the sale does not put the product back on sale.
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_regular_user_cannot_strike_a_sale(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        sale = Sale.objects.get(product=product)
        self.client.logout()
        self.client.force_login(User.objects.create_user(username='shopper', password='shopper-password-123'))

        self.client.post(reverse('shop:discard_sale', args=[sale.id]))

        self.assertTrue(Sale.objects.filter(pk=sale.pk).exists())

    def test_regular_user_cannot_restore_a_removed_product(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        self.client.logout()

        buyer = User.objects.create_user(username='buyer', password='safe-password-123')
        self.client.force_login(buyer)
        self.client.post(reverse('shop:restore_product', args=[product.id]))

        product.refresh_from_db()
        self.assertIsNotNone(product.deleted_at)

    def test_a_removed_product_keeps_its_slug_and_catalog_number_reserved(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        removed = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[removed.id]))

        self.client.post(reverse('shop:create_product'), {
            'category': self.category.id, 'brand': 'Example', 'name': 'Phone',
            'price': '300.00', 'description': 'A replacement listing.', 'slug': '',
        })

        replacement = Product.objects.get(price=Decimal('300.00'))
        self.assertNotEqual(replacement.slug, removed.slug)
        self.assertNotEqual(replacement.category_number, removed.category_number)

    def test_removed_product_is_absent_from_catalog_and_api(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))

        self.assertEqual(len(self.client.get(reverse('shop:product_list')).context['products']), 0)
        self.assertEqual(self.client.get('/api/products/').json()['results'], [])

    def test_api_list_is_paginated_and_avoids_a_query_per_product(self):
        for i in range(6):
            self.make_product(f'Phone {i}', f'phone-{i}', '100.00')

        with self.assertNumQueries(2):  # one count for paging, one for the page
            payload = self.client.get('/api/products/').json()

        self.assertEqual(payload['count'], 6)
        self.assertIn('results', payload)
        # The nested category must come from the join, not a lookup per row.
        self.assertEqual(payload['results'][0]['category']['slug'], 'phones')

    def test_homepage_gets_a_row_for_every_category_with_stock(self):
        headphones = Category.objects.create(name='Headphones', slug='headphones')
        Product.objects.create(
            category=headphones,
            brand='Sony',
            name='WH-1000XM5',
            slug='wh-1000xm5',
            price=Decimal('349.00'),
            description='Noise-cancelling headphones.',
        )
        self.make_product('Phone', 'phone', '100.00')

        response = self.client.get(reverse('shop:home'))

        sections = {s['category'].slug: s for s in response.context['category_sections']}
        self.assertIn('headphones', sections)
        self.assertIn('phones', sections)
        self.assertContains(response, 'Newest In Headphones')

    def login_as_manager(self):
        staff = User.objects.create_user(
            username='manager', password='manager-password-123', is_staff=True
        )
        self.client.force_login(staff)
        return staff

    def test_purging_a_removed_listing_erases_the_row_for_good(self):
        self.login_as_manager()
        product = self.make_product('Added by mistake', 'mistake', '250.00')
        self.client.post(reverse('shop:remove_product', args=[product.id]))

        self.client.post(reverse('shop:purge_product', args=[product.id]))

        # Not merely hidden this time: the row itself is gone, so the slug and
        # the per-category number are free again.
        self.assertFalse(Product.all_objects.filter(pk=product.pk).exists())

    def test_purging_is_refused_for_a_listing_still_on_the_catalog(self):
        self.login_as_manager()
        product = self.make_product('Phone', 'phone', '250.00')

        response = self.client.post(reverse('shop:purge_product', args=[product.id]))

        # Permanent delete is only reachable from "Removed", so no
        # active listing can be erased in a single click.
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Product.all_objects.filter(pk=product.pk).exists())


    def test_purging_a_sold_listing_leaves_its_sale_in_the_report(self):
        self.login_as_manager()
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))

        self.client.post(reverse('shop:purge_product', args=[product.id]))

        self.assertFalse(Product.all_objects.filter(pk=product.pk).exists())
        # Sale.product is SET_NULL and the figures are snapshotted on the Sale,
        # so a past month's revenue survives the listing being erased.
        sale = Sale.objects.get(product_name='Phone')
        self.assertIsNone(sale.product)
        self.assertEqual(sale.price, Decimal('250.00'))

    def test_deleting_a_category_takes_its_products_with_it(self):
        self.login_as_manager()
        active = self.make_product('Phone', 'phone', '250.00')
        removed = self.make_product('Old Phone', 'old-phone', '100.00')
        self.client.post(reverse('shop:remove_product', args=[removed.id]))

        self.client.post(reverse('shop:delete_category', args=[self.category.id]))

        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())
        # Everything filed under it goes, a parked listing included.
        self.assertFalse(Product.all_objects.filter(pk=active.pk).exists())
        self.assertFalse(Product.all_objects.filter(pk=removed.pk).exists())

    def test_deleting_a_category_keeps_the_sales_it_recorded(self):
        self.login_as_manager()
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))

        self.client.post(reverse('shop:delete_category', args=[self.category.id]))

        sale = Sale.objects.get(product_name='Phone')
        self.assertIsNone(sale.product)
        self.assertEqual(sale.price, Decimal('250.00'))


    def test_archive_lists_every_sale_including_one_whose_listing_was_purged(self):
        self.login_as_manager()
        kept = self.make_product('Kept Phone', 'kept-phone', '250.00')
        purged = self.make_product('Purged Phone', 'purged-phone', '400.00')
        self.client.post(reverse('shop:sell_product', args=[kept.id]))
        self.client.post(reverse('shop:sell_product', args=[purged.id]))
        self.client.post(reverse('shop:purge_product', args=[purged.id]))

        response = self.client.get(reverse('shop:sales_archive'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['total_revenue'], Decimal('650.00'))
        self.assertContains(response, 'Kept Phone')
        self.assertContains(response, 'Purged Phone')

    def test_about_page_counts_stock_categories_and_brands(self):
        laptops = Category.objects.create(name='Laptops', slug='laptops')
        Category.objects.create(name='Empty', slug='empty')
        self.make_product('Older Phone', 'older-phone', '400.00')
        self.make_product('Newest Phone', 'newest-phone', '500.00')
        Product.objects.create(category=laptops, brand='Other', name='Laptop', slug='laptop', price=Decimal('900.00'))
        sold = self.make_product('Sold Phone', 'sold-phone', '100.00')
        sold.is_sold = True
        sold.save(update_fields=['is_sold'])

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('shop:about_us'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['in_stock_count'], 3)
        self.assertEqual(response.context['category_count'], 2)
        self.assertEqual(response.context['brand_count'], 2)
        # One catalog pass serves all three figures.
        product_queries = [q for q in queries.captured_queries if '"shop_product"' in q['sql']]
        self.assertEqual(len(product_queries), 1)

    def test_about_page_shows_hours_and_directions_only_when_set(self):
        contact = ContactSettings.get_solo()
        contact.whatsapp_number = '996700123456'
        contact.save()
        settings_obj = AboutPageContent.get_solo()

        response = self.client.get(reverse('shop:about_us'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Opening hours')
        self.assertNotContains(response, 'Get directions')

        settings_obj.opening_hours = 'Mon-Sat 10:00-20:00'
        settings_obj.opening_hours_ru = 'Пн-Сб 10:00-20:00'
        settings_obj.map_url = 'https://maps.example.com/store'
        settings_obj.save()

        response = self.client.get(reverse('shop:about_us'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(response, 'Mon-Sat 10:00-20:00')
        self.assertContains(response, 'https://maps.example.com/store')

        # The hours follow the visitor's language, falling back to English.
        response = self.client.get(reverse('shop:about_us'), HTTP_ACCEPT_LANGUAGE='ru')
        self.assertContains(response, 'Пн-Сб 10:00-20:00')
        response = self.client.get(reverse('shop:about_us'), HTTP_ACCEPT_LANGUAGE='ky')
        self.assertContains(response, 'Mon-Sat 10:00-20:00')


class ManagementPanelTests(TestCase):
    """The in-app management panel: its sidebar, the homepage section editor,
    the removed-listings page, and the merged sales page."""

    def setUp(self):
        self.category = Category.objects.create(name='Phones', slug='phones')
        self.staff = User.objects.create_user(
            username='manager', password='manager-password-123', is_staff=True
        )
        self.client.force_login(self.staff)

    def make_product(self, name, slug, price):
        return Product.objects.create(
            category=self.category, brand='Example', name=name, slug=slug,
            price=Decimal(price), description='A tested product.',
        )

    # --- products browser ---------------------------------------------

    def test_products_page_lists_categories_then_opens_one(self):
        laptops = Category.objects.create(name='Laptops', slug='laptops')
        phone = self.make_product('Phone', 'phone', '250.00')
        Product.objects.create(category=laptops, brand='Other', name='Laptop', slug='laptop', price=Decimal('900.00'))

        # Top level: the category list, no listings.
        response = self.client.get(reverse('shop:create_product'))
        self.assertIsNone(response.context['selected_group'])
        self.assertEqual([g['category'].slug for g in response.context['category_groups']], ['laptops', 'phones'])
        self.assertContains(response, '?category=phones')
        self.assertNotContains(response, 'name="category"')

        # Pressing one: its listings, and only its.
        response = self.client.get(reverse('shop:create_product'), {'category': 'phones'})
        self.assertEqual(response.context['selected_group']['products'], [phone])
        self.assertContains(response, 'name="category" value="phones"')
        self.assertNotContains(response, 'name="category" value="laptops"')

        # An unknown slug shows the list rather than 404ing.
        response = self.client.get(reverse('shop:create_product'), {'category': 'nope'})
        self.assertIsNone(response.context['selected_group'])

    def test_products_search_spans_every_category(self):
        laptops = Category.objects.create(name='Laptops', slug='laptops')
        self.make_product('Galaxy Phone', 'galaxy-phone', '250.00')
        self.make_product('Other Phone', 'other-phone', '250.00')
        Product.objects.create(category=laptops, brand='Galaxy Works', name='Book', slug='book', price=Decimal('900.00'))

        response = self.client.get(reverse('shop:create_product'), {'q': 'galaxy'})

        groups = {g['category'].slug: [p.slug for p in g['products']] for g in response.context['search_groups']}
        self.assertEqual(groups, {'laptops': ['book'], 'phones': ['galaxy-phone']})

        response = self.client.get(reverse('shop:create_product'), {'q': '#1'})
        groups = {g['category'].slug: [p.slug for p in g['products']] for g in response.context['search_groups']}
        self.assertEqual(groups, {'phones': ['other-phone']})

    def test_marking_sold_returns_to_the_category_it_happened_in(self):
        product = self.make_product('Phone', 'phone', '250.00')

        response = self.client.post(reverse('shop:sell_product', args=[product.id]), {'category': 'phones'})

        self.assertRedirects(response, reverse('shop:create_product') + '?category=phones')

    # --- background actions ------------------------------------------

    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def test_actions_posted_in_the_background_answer_with_json_not_a_redirect(self):
        product = self.make_product('Phone', 'phone', '250.00')

        response = self.client.post(reverse('shop:sell_product', args=[product.id]), {'category': 'phones'}, **self.AJAX)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['removed_count'], 1)
        self.assertEqual(data['messages'][0]['level'], 'success')
        self.assertIn('Phone', data['messages'][0]['text'])
        # The flash was handed over in the JSON, so it must not show up on
        # the next full page as well.
        self.assertNotContains(self.client.get(reverse('shop:create_product')), 'was marked as sold')

        # The same post without the header still redirects, as before.
        product = self.make_product('Other', 'other', '250.00')
        response = self.client.post(reverse('shop:sell_product', args=[product.id]))
        self.assertEqual(response.status_code, 302)

    def test_adding_a_product_in_the_background_reports_errors_or_success(self):
        response = self.client.post(reverse('shop:create_product'), {'name': ''}, **self.AJAX)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('name', [error['field'] for error in data['errors']])
        self.assertFalse(Product.objects.exists())

        response = self.client.post(reverse('shop:create_product'), {
            'name': 'Phone', 'slug': 'phone', 'brand': 'Example', 'category': self.category.id,
            'price': '250.00', 'description': 'A phone.',
        }, **self.AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertTrue(Product.objects.filter(slug='phone').exists())

    # --- technical characteristics ------------------------------------

    def post_product(self, specs, product=None):
        """Save a product with the given (name, value) characteristic rows."""
        url = reverse('shop:update_product', args=[product.id]) if product else reverse('shop:create_product')
        return self.client.post(url, {
            'name': 'Charger', 'slug': 'charger', 'brand': 'Example', 'category': self.category.id,
            'price': '20.00', 'description': 'A charger.',
            'spec_name': [name for name, _ in specs], 'spec_value': [value for _, value in specs],
        }, **self.AJAX)

    def test_a_product_can_be_added_with_its_own_characteristics_or_none(self):
        self.assertTrue(self.post_product([('Model', 'A2305'), ('', '')]).json()['ok'])
        self.assertEqual(Product.objects.get(slug='charger').specifications, {'Model': 'A2305'})

        Product.objects.all().delete()
        self.assertTrue(self.post_product([]).json()['ok'])
        self.assertEqual(Product.objects.get(slug='charger').specifications, {})

    def test_characteristics_stay_editable_after_the_product_is_added(self):
        product = self.make_product('Phone', 'phone', '250.00')
        product.specifications = {'RAM': '8 GB', 'CPU': 'A17'}
        product.save()

        response = self.client.get(reverse('shop:update_product', args=[product.id]))
        self.assertContains(response, 'value="RAM"')
        self.assertContains(response, 'value="A17"')

        self.post_product([('CPU', 'A17 Pro'), ('Camera', '48 MP')], product=product)
        product.refresh_from_db()
        self.assertEqual(list(product.specifications.items()), [('CPU', 'A17 Pro'), ('Camera', '48 MP')])

    def test_a_half_filled_or_repeated_characteristic_is_refused(self):
        for specs in ([('RAM', '')], [('', '8 GB')], [('RAM', '8 GB'), ('ram', '16 GB')]):
            response = self.post_product(specs)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.exists())

    def test_catalog_cards_do_not_list_characteristics(self):
        product = self.make_product('Phone', 'phone', '250.00')
        product.specifications = {'RAM': '8 GB'}
        product.save()

        self.assertNotContains(self.client.get(reverse('shop:product_list')), 'RAM: 8 GB')
        self.assertContains(self.client.get(reverse('shop:product_detail', args=[product.slug])), '8 GB')

    def test_category_actions_in_the_background_hand_back_the_row(self):
        response = self.client.post(reverse('shop:create_category'), {'name': 'Laptops', 'slug': 'laptops'}, **self.AJAX)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        laptops = Category.objects.get(slug='laptops')
        self.assertIn(f'data-row="category-{laptops.id}"', data['html'])
        self.assertEqual(data['category_count'], 2)

        response = self.client.post(reverse('shop:toggle_category_hero', args=[laptops.id]), **self.AJAX)
        data = response.json()
        self.assertIn('aria-checked="true"', data['html'])
        self.assertTrue(Category.objects.get(pk=laptops.pk).is_featured_in_hero)

        response = self.client.post(reverse('shop:delete_category', args=[laptops.id]), **self.AJAX)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['category_count'], 1)

    # --- sidebar -------------------------------------------------------

    def test_every_management_page_renders_with_the_shared_sidebar(self):
        pages = [
            ('shop:create_product', 'products'),
            ('shop:create_category', 'categories'),
            ('shop:removed_products', 'removed'),
            ('shop:sales_archive', 'sales'),
            ('shop:manage_homepage', 'homepage'),
            ('shop:manage_about', 'about'),
            ('shop:manage_contacts', 'contacts'),
        ]
        for name, active in pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                # The lit link is chosen from this key, so it has to survive.
                self.assertEqual(response.context['active'], active)
                # Every page can reach every other one from the sidebar.
                for other, _unused in pages:
                    self.assertContains(response, reverse(other))

        # The monthly view isn't in the sidebar — the sales page switches to
        # it itself — but it still lights the one Sales entry.
        response = self.client.get(reverse('shop:sales_report'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active'], 'sales')
        self.assertContains(response, reverse('shop:sales_archive'))

    def test_section_pages_drill_down_on_phones(self):
        """Below `lg` a section page shows only its own content: the section
        list is hidden and a Back link leads to the panel's front door. From
        `lg` up the same list is the sidebar beside the page."""
        for name in ('shop:create_product', 'shop:sales_archive', 'shop:manage_contacts'):
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()

                menu = re.search(r'id="section-menu"[^>]*class="([^"]*)"', html)
                self.assertIsNotNone(menu)
                self.assertIn('hidden', menu.group(1))
                self.assertIn('lg:block', menu.group(1))

                content = re.search(r'id="section-content"[^>]*class="([^"]*)"', html)
                self.assertIsNotNone(content)
                self.assertNotIn('hidden', content.group(1))

                self.assertContains(
                    self.client.get(reverse(name)),
                    f'href="{reverse("shop:management_home")}"',
                )

    def test_management_home_is_the_section_list_on_phones(self):
        """The front door passes no `active` key, so below `lg` it is the
        full-width section list and nothing else; from `lg` up the list is
        the sidebar and an overview of the same sections sits beside it."""
        response = self.client.get(reverse('shop:management_home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('active', response.context)
        html = response.content.decode()

        menu = re.search(r'id="section-menu"[^>]*class="([^"]*)"', html)
        self.assertIsNotNone(menu)
        self.assertNotIn('hidden', menu.group(1))

        content = re.search(r'id="section-content"[^>]*class="([^"]*)"', html)
        self.assertIsNotNone(content)
        self.assertIn('hidden', content.group(1))
        self.assertIn('lg:block', content.group(1))

        # Every section is reachable from here, in both layouts.
        for group in response.context['management_groups']:
            for item in group['items']:
                self.assertContains(response, item['url'])

    def test_management_home_requires_a_manager(self):
        self.client.logout()
        response = self.client.get(reverse('shop:management_home'))
        self.assertEqual(response.status_code, 302)

    def test_every_nav_link_is_defined_once_for_both_layouts(self):
        """The sidebar and the collapsed row read one list, so a page added to
        the panel shows up in both without being spelled out twice."""
        response = self.client.get(reverse('shop:manage_about'))

        keys = [item['key'] for group in response.context['management_groups']
                for item in group['items']]
        self.assertEqual(
            keys,
            ['products', 'categories', 'removed', 'sales', 'homepage', 'about', 'contacts'],
        )
        # Every view's `active` key has to be one of them, or nothing lights up.
        self.assertIn(response.context['active'], keys)

    def test_sidebar_badge_counts_removed_listings_only_on_the_panel(self):
        self.make_product('Gone', 'gone', '100.00')
        self.client.post(reverse('shop:remove_product', args=[Product.all_objects.get(slug='gone').id]))

        panel = self.client.get(reverse('shop:manage_about'))
        self.assertEqual(panel.context['removed_count'], 1)

        # The storefront renders no sidebar, so it must not pay for the count.
        self.assertNotIn('removed_count', self.client.get(reverse('shop:home')).context)

    # --- homepage sections ---------------------------------------------

    def test_homepage_bands_render_from_the_editable_content(self):
        content = HomePageContent.get_solo()
        content.promise_card_heading = 'We check every device'
        content.invite_heading = 'Ask us for any model'
        content.save()

        response = self.client.get(reverse('shop:home'))

        self.assertContains(response, 'We check every device')
        self.assertContains(response, 'Ask us for any model')

    def post_homepage_form(self, **overrides):
        """POST the homepage editor the way the browser does: every field
        present, blank ones included. Django's construct_instance keeps a
        model default for a field left out of the data entirely, so a test
        that posts a subset would never exercise clearing one."""
        from .forms import HomePageContentForm

        data = {name: '' for name in HomePageContentForm.Meta.fields}
        data['site_name'] = 'TechVault'  # required; the only field that is
        data.update(overrides)
        return self.client.post(reverse('shop:manage_homepage'), data, follow=True)

    def test_staff_can_rewrite_the_homepage_bands(self):
        response = self.post_homepage_form(
            promise_heading='Why us',
            promise_card_heading='Honest prices',
            promise_text='Everything on the shelf.',
            promise_button_text='See the catalog',
            promise_stat_label='phones ready',
            promise_stat_caption='New stock weekly',
            invite_eyebrow='Cannot find it',
            invite_heading='We will order it',
            invite_text='Tell us the model.',
            invite_button_text='Message us',
        )

        self.assertEqual(response.status_code, 200)
        content = HomePageContent.get_solo()
        self.assertEqual(content.promise_card_heading, 'Honest prices')
        self.assertEqual(content.invite_heading, 'We will order it')
        # A translation cleared in the form falls back to the base language
        # rather than blanking that line on the live page.
        self.assertEqual(content.promise_card_heading_ru, '')
        self.assertEqual(content.translated_promise_card_heading, 'Honest prices')
        with translation.override('ru'):
            self.assertEqual(content.translated_promise_card_heading, 'Honest prices')

    def test_a_kept_translation_still_wins_over_the_base_language(self):
        self.post_homepage_form(
            promise_card_heading='Honest prices',
            promise_card_heading_ru='Честные цены',
        )

        content = HomePageContent.get_solo()
        with translation.override('ru'):
            self.assertEqual(content.translated_promise_card_heading, 'Честные цены')

    def test_homepage_band_defaults_are_translated_not_english(self):
        content = HomePageContent.get_solo()
        self.assertTrue(content.promise_card_heading_ru)
        self.assertTrue(content.invite_heading_ky)

        with translation.override('ru'):
            self.assertEqual(
                content.translated_promise_card_heading, content.promise_card_heading_ru
            )

    def test_clearing_a_button_label_hides_that_button(self):
        content = HomePageContent.get_solo()
        content.promise_button_text = ''
        content.promise_button_text_ru = ''
        content.promise_button_text_ky = ''
        content.save()

        response = self.client.get(reverse('shop:home'))

        self.assertNotContains(response, 'Browse the catalog')

    def test_management_panel_speaks_russian(self):
        """The panel's own chrome is translated, not just the storefront —
        a fuzzy or missing catalog entry would silently fall back to English."""
        response = self.client.get(reverse('shop:manage_homepage'), headers={'accept-language': 'ru'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Блоки главной страницы')
        self.assertContains(response, 'Удалённые')

    def test_regular_user_cannot_edit_the_homepage(self):
        self.client.force_login(User.objects.create_user(username='shopper', password='shopper-pass-123'))

        response = self.client.get(reverse('shop:manage_homepage'))

        self.assertRedirects(response, reverse('shop:product_list'))

    # --- removed listings ----------------------------------------------

    def test_removed_page_lists_every_removal_and_labels_how_it_happened(self):
        sold = self.make_product('Sold Phone', 'sold-phone', '250.00')
        deleted = self.make_product('Mistake', 'mistake', '100.00')
        self.client.post(reverse('shop:sell_product', args=[sold.id]))
        self.client.post(reverse('shop:remove_product', args=[deleted.id]))

        response = self.client.get(reverse('shop:removed_products'))

        by_pk = {p.pk: p for p in response.context['removed_products']}
        self.assertTrue(by_pk[sold.pk].was_sold)
        self.assertFalse(by_pk[deleted.pk].was_sold)
        self.assertEqual(response.context['sold_count'], 1)
        self.assertEqual(response.context['deleted_count'], 1)

    def test_removed_page_search_narrows_the_list_and_its_tallies(self):
        keep = self.make_product('Galaxy Phone', 'galaxy', '250.00')
        other = self.make_product('Laptop', 'laptop', '900.00')
        self.client.post(reverse('shop:remove_product', args=[keep.id]))
        self.client.post(reverse('shop:remove_product', args=[other.id]))

        response = self.client.get(reverse('shop:removed_products'), {'search': 'galaxy'})

        self.assertEqual([p.pk for p in response.context['removed_products']], [keep.pk])
        self.assertEqual(response.context['shown_count'], 1)
        # The sidebar badge keeps showing everything that is actually removed.
        self.assertEqual(response.context['removed_count'], 2)

    def test_restoring_from_the_removed_page_comes_back_to_it(self):
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:remove_product', args=[product.id]))

        response = self.client.post(
            reverse('shop:restore_product', args=[product.id]), {'next': 'removed'}
        )

        self.assertRedirects(response, reverse('shop:removed_products'))
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_a_catalog_action_without_a_next_still_lands_on_products(self):
        product = self.make_product('Phone', 'phone', '250.00')

        response = self.client.post(reverse('shop:remove_product', args=[product.id]))

        self.assertRedirects(response, reverse('shop:create_product'))

    def test_removed_listings_are_annotated_without_a_query_each(self):
        for index in range(5):
            product = self.make_product(f'Phone {index}', f'phone-{index}', '250.00')
            self.client.post(reverse('shop:sell_product', args=[product.id]))

        # One query for the listings, one for the sales behind them — not one
        # sale lookup per listing.
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('shop:removed_products'))
        self.assertEqual(len(response.context['removed_products']), 5)
        sale_queries = [q for q in queries.captured_queries if '"shop_sale"' in q['sql']]
        self.assertEqual(len(sale_queries), 1)

    # --- merged sales page ----------------------------------------------

    def test_all_time_view_is_staff_only_though_it_has_no_decorator_of_its_own(self):
        """sales_archive delegates straight to the decorated sales_report, so
        its access check has to come along with it."""
        self.client.force_login(User.objects.create_user(username='shopper', password='shopper-pass-123'))

        response = self.client.get(reverse('shop:sales_archive'))

        self.assertRedirects(response, reverse('shop:product_list'))

    def test_month_view_and_all_time_view_share_one_page(self):
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))

        month = self.client.get(reverse('shop:sales_report'))
        self.assertEqual(month.context['period'], 'month')
        self.assertEqual(month.context['total_count'], 1)

        all_time = self.client.get(reverse('shop:sales_archive'))
        self.assertEqual(all_time.context['period'], 'all')
        self.assertEqual(all_time.context['total_count'], 1)
        self.assertEqual(all_time.templates[0].name, month.templates[0].name)

    def test_all_time_view_includes_sales_outside_the_current_month(self):
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        old = Sale.objects.get()
        Sale.objects.filter(pk=old.pk).update(sold_at=timezone.now() - timedelta(days=400))

        self.assertEqual(self.client.get(reverse('shop:sales_report')).context['total_count'], 0)
        self.assertEqual(self.client.get(reverse('shop:sales_archive')).context['total_count'], 1)

    def test_all_time_view_can_be_searched(self):
        keep = self.make_product('Galaxy Phone', 'galaxy', '250.00')
        other = self.make_product('Laptop', 'laptop', '900.00')
        self.client.post(reverse('shop:sell_product', args=[keep.id]))
        self.client.post(reverse('shop:sell_product', args=[other.id]))

        response = self.client.get(reverse('shop:sales_archive'), {'search': 'galaxy'})

        self.assertEqual(response.context['total_count'], 1)
        self.assertEqual(response.context['total_revenue'], Decimal('250.00'))

    def test_breakdowns_group_by_one_column_not_by_sale_date(self):
        first = self.make_product('Phone One', 'phone-one', '100.00')
        second = self.make_product('Phone Two', 'phone-two', '150.00')
        self.client.post(reverse('shop:sell_product', args=[first.id]))
        self.client.post(reverse('shop:sell_product', args=[second.id]))

        response = self.client.get(reverse('shop:sales_archive'))

        by_category = list(response.context['by_category'])
        self.assertEqual(len(by_category), 1)
        self.assertEqual(by_category[0]['count'], 2)
        self.assertEqual(by_category[0]['total'], Decimal('250.00'))

    def test_striking_a_sale_from_the_all_time_view_returns_to_it(self):
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        sale = Sale.objects.get()

        response = self.client.post(
            reverse('shop:discard_sale', args=[sale.id]), {'period': 'all'}
        )

        self.assertRedirects(response, reverse('shop:sales_archive'))
        self.assertFalse(Sale.objects.exists())
