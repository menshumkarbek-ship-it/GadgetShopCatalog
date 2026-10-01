import io
import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.conf import settings
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation

from .models import AboutPageContent, Category, ContactSettings, HomePageContent, Product, ProductImage, Sale


def in_language(client, language):
    """Pick a language the way a visitor does: the switcher's cookie."""
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = language


class TranslationCatalogTests(TestCase):
    """Every string marked for translation has a Russian and a Kyrgyz version.
    A fuzzy entry is a guess the site ignores, so visitors would see English:
    after adding text to a template, run makemessages and translate it."""

    def entries(self, language):
        import re
        from pathlib import Path
        path = Path(settings.BASE_DIR) / 'locale' / language / 'LC_MESSAGES' / 'django.po'
        blocks = re.split(r'\n\s*\n', path.read_text(encoding='utf-8'))
        for block in blocks[1:]:  # the first block is the file header
            if block.lstrip().startswith('#~') or 'msgid ' not in block:
                continue
            yield block

    def test_no_string_is_left_untranslated_or_fuzzy(self):
        import re
        for language in ('ru', 'ky'):
            for block in self.entries(language):
                msgid = re.search(r'^msgid "(.*)"', block, flags=re.M).group(1)[:60]
                with self.subTest(language=language, msgid=msgid):
                    self.assertNotRegex(block, r'(?m)^#,.*fuzzy', 'marked fuzzy')
                    # each msgstr, with any continuation lines that follow it
                    translations = re.findall(r'(?ms)^msgstr(?:\[\d\])? ((?:"[^\n]*"\n?)+)', block + '\n')
                    self.assertTrue(translations)
                    for text in translations:
                        self.assertNotEqual(''.join(re.findall(r'"(.*)"', text)), '', 'no translation')


class DefaultLanguageTests(TestCase):
    """The store is Russian-first: the browser's language is ignored, and
    only the navbar switcher changes it."""

    def test_a_first_visit_is_in_russian_whatever_the_browser_asks_for(self):
        response = self.client.get(reverse('shop:product_list'), HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, 'ru')
        self.assertContains(response, '<html lang="ru">')
        self.assertEqual(response['Content-Language'], 'ru')

    def test_the_switcher_choice_sticks(self):
        response = self.client.post(reverse('set_language'), {'language': 'en', 'next': '/'})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('shop:product_list'))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, 'en')

        in_language(self.client, 'ky')
        self.assertEqual(self.client.get(reverse('shop:product_list')).wsgi_request.LANGUAGE_CODE, 'ky')

    def test_an_unknown_language_cookie_falls_back_to_russian(self):
        in_language(self.client, 'de')
        self.assertEqual(self.client.get(reverse('shop:product_list')).wsgi_request.LANGUAGE_CODE, 'ru')


# The suites below assert English copy, so they run with English as the
# default; DefaultLanguageTests above covers the real (Russian) one.
@override_settings(LANGUAGE_CODE='en')
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

    # --- switching languages on and off ---------------------------------

    def _languages(self, **switches):
        """Save the language switches the way the panel does."""
        from .models import LanguageSettings
        data = {name: 'on' for name in ('english', 'russian', 'kyrgyz')}
        for name, on in switches.items():
            if on:
                data[name] = 'on'
            else:
                data.pop(name, None)
        return self.client.post(reverse('shop:manage_languages'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_admin_can_switch_languages_off_and_the_site_follows(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        # Everything is on to begin with, and the switcher offers all three.
        home = self.client.get(reverse('shop:home'))
        for name in ('English', 'Русский', 'Кыргызча'):
            self.assertContains(home, f'>{name}</option>')

        # Turn English and Kyrgyz off: only Russian is left, so no switcher.
        self.assertTrue(self._languages(english=False, kyrgyz=False).json()['ok'])
        visitor = self.client_class()
        page = visitor.get(reverse('shop:home'))
        self.assertNotContains(page, 'id="language-switcher-form"')
        self.assertEqual(page.wsgi_request.LANGUAGE_CODE, 'ru')

        # A visitor whose cookie still names a language that is off gets Russian.
        in_language(visitor, 'en')
        self.assertEqual(visitor.get(reverse('shop:home')).wsgi_request.LANGUAGE_CODE, 'ru')

        # Only Kyrgyz on: it becomes the language everyone is served.
        self.assertTrue(self._languages(russian=False, english=False, kyrgyz=True).json()['ok'])
        page = self.client_class().get(reverse('shop:home'))
        self.assertEqual(page.wsgi_request.LANGUAGE_CODE, 'ky')

        # Russian and English on: the switcher offers just those two.
        self._languages(kyrgyz=False)
        page = self.client_class().get(reverse('shop:home'))
        self.assertContains(page, '>English</option>')
        self.assertContains(page, '>Русский</option>')
        self.assertNotContains(page, '>Кыргызча</option>')

    def test_at_least_one_language_must_stay_on(self):
        from .models import LanguageSettings
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)

        refused = self._languages(english=False, russian=False, kyrgyz=False)
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(LanguageSettings.get_solo().enabled_codes, ['en', 'ru', 'ky'])

    def test_sign_out_is_the_last_card_on_a_phone(self):
        staff = User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get(reverse('shop:management_home')).content.decode()

        # Sign Out takes order-5 (last) on a phone and joins the Sales row on
        # a wide screen; Languages is the card after the Site label.
        self.assertIn('data-reload class="order-5 lg:order-2"', html)
        self.assertIn(reverse('shop:manage_languages'), html)
        self.assertLess(html.index(reverse('shop:sold_products')), html.index('order-5 lg:order-2'))

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

    def test_signing_in_from_the_plain_page_lands_on_the_home_page(self):
        User.objects.create_user(username='manager', password='manager-password-123', is_staff=True)
        for address in (reverse('admin:login'), '/admin/', f"{reverse('admin:login')}?next=/admin/"):
            with self.subTest(address=address):
                self.client.logout()
                page = self.client.get(reverse('admin:login'), {'next': address} if address.startswith('/admin/') else {})
                self.assertContains(page, f'name="next" value="{reverse("shop:home")}"')
        # Coming from a protected page still goes back to it.
        page = self.client.get(reverse('admin:login'), {'next': reverse('shop:management_home')})
        self.assertContains(page, f'name="next" value="{reverse("shop:management_home")}"')

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

        response = self.client.post(reverse('shop:create_category'), {'name': 'Headphones', 'slug': '', 'id_prefix': 'H', 'id_digits': '1'}, follow=True)

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

        self.client.post(reverse('shop:create_category'), {'name': 'Наушники', 'slug': '', 'id_prefix': 'Н', 'id_digits': '1'})

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
            'price': '199',
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
            'name': 'Powerbanks', 'slug': '', 'id_prefix': 'PB', 'id_digits': '1', 'is_featured_in_hero': 'on',
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

    def test_missing_page_gets_the_branded_404(self):
        response = self.client.get('/product/no-such-device/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertContains(response, reverse('shop:product_list'), status_code=404)

    def test_pages_load_the_built_stylesheet_not_the_tailwind_cdn(self):
        response = self.client.get(reverse('shop:home'))
        self.assertContains(response, 'shop/css/site.css')
        self.assertNotContains(response, 'cdn.tailwindcss.com')

    def test_favicon_is_served(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 301)
        self.assertIn('shop/favicon', response['Location'])

    def test_500_page_renders_without_a_request(self):
        from django.template.loader import get_template
        html = get_template('500.html').render()
        self.assertIn('Something went wrong', html)

    def test_sitemap_lists_categories_and_products_on_sale_only(self):
        on_sale = self.make_product('Phone', 'phone', '100.00')
        sold = self.make_product('Sold Phone', 'sold-phone', '100.00')
        sold.is_sold = True
        sold.save()

        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('shop:product_detail', args=[on_sale.slug]))
        self.assertContains(response, reverse('shop:product_list_by_category', args=[self.category.slug]))
        self.assertNotContains(response, reverse('shop:product_detail', args=[sold.slug]))

    def test_nonsense_price_filters_are_ignored_not_a_500(self):
        self.make_product('Phone', 'phone', '100.00')
        for value in ('nan', 'inf', '-inf', '1e999', 'abc', '-5'):
            with self.subTest(value=value):
                response = self.client.get(reverse('shop:product_list'), {'min_price': value, 'max_price': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context['products']), 1)

        response = self.client.get(reverse('shop:product_list'), {'min_price': '150'})
        self.assertEqual(len(response.context['products']), 0)

    def test_catalog_search_finds_a_listing_by_its_russian_title(self):
        product = self.make_product('Galaxy Buds', 'galaxy-buds', '100.00')
        product.name_ru = 'Беспроводные наушники'
        product.save()

        response = self.client.get(reverse('shop:product_list'), {'search': 'наушники'})
        self.assertEqual([p.pk for p in response.context['products']], [product.pk])

    def test_kyrgyz_shows_kyrgyz_text_then_russian_then_the_main_text(self):
        product = self.make_product('Phone', 'phone', '100.00')
        url = reverse('shop:product_detail', args=[product.slug])
        in_language(self.client, 'ky')

        # Nothing translated: the main text.
        self.assertContains(self.client.get(url), 'A tested product.')
        # Russian only: Kyrgyz readers get the Russian.
        product.description_ru = 'Проверенный товар.'
        product.save()
        self.assertContains(self.client.get(url), 'Проверенный товар.')
        # Kyrgyz written: that wins.
        product.description_ky = 'Текшерилген товар.'
        product.save()
        response = self.client.get(url)
        self.assertContains(response, 'Текшерилген товар.')
        self.assertNotContains(response, 'Проверенный товар.')
        # Russian and English visitors are unaffected.
        in_language(self.client, 'ru')
        self.assertContains(self.client.get(url), 'Проверенный товар.')
        in_language(self.client, 'en')
        self.assertContains(self.client.get(url), 'A tested product.')

    def test_product_id_is_shown_on_the_product_page_only(self):
        self.category.id_prefix = 'L'
        self.category.id_digits = 3
        self.category.save()
        product = self.make_product('Phone', 'phone', '100.00')
        self.assertEqual(product.catalog_code, 'L-001')

        self.assertContains(self.client.get(reverse('shop:product_detail', args=[product.slug])), 'L-001')
        for page in (reverse('shop:home'), reverse('shop:product_list'),
                     reverse('shop:product_list_by_category', args=[self.category.slug])):
            with self.subTest(page=page):
                self.assertNotContains(self.client.get(page), 'L-001')

    def test_language_switcher_names_each_language_in_itself(self):
        response = self.client.get(reverse('shop:home'))
        # Drawn as the site's own dropdown, not the browser's.
        self.assertContains(response, 'shop/js/dropdowns.js')
        for name in ('English', 'Русский', 'Кыргызча'):
            self.assertContains(response, f'>{name}</option>')

    def test_about_page_shows_hours_and_directions_only_when_set(self):
        contact = ContactSettings.get_solo()
        contact.whatsapp_number = '996700123456'
        contact.save()
        settings_obj = AboutPageContent.get_solo()

        response = self.client.get(reverse('shop:about_us'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Opening hours')
        self.assertNotContains(response, 'Get directions')

        settings_obj.opening_hours = 'Mon-Sat 10:00-20:00'
        settings_obj.opening_hours_ru = 'Пн-Сб 10:00-20:00'
        settings_obj.map_url = 'https://maps.example.com/store'
        settings_obj.save()

        response = self.client.get(reverse('shop:about_us'))
        self.assertContains(response, 'Mon-Sat 10:00-20:00')
        self.assertContains(response, 'https://maps.example.com/store')

        # The hours follow the visitor's language; Kyrgyz with none of its
        # own falls back to Russian.
        in_language(self.client, 'ru')
        response = self.client.get(reverse('shop:about_us'))
        self.assertContains(response, 'Пн-Сб 10:00-20:00')
        in_language(self.client, 'ky')
        response = self.client.get(reverse('shop:about_us'))
        self.assertContains(response, 'Пн-Сб 10:00-20:00')


@override_settings(LANGUAGE_CODE='en')
class ManagementPanelTests(TestCase):
    """The in-app management panel: its section cards, the homepage section editor,
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

        response = self.client.get(reverse('shop:create_product'), {'q': '#2'})
        groups = {g['category'].slug: [p.slug for p in g['products']] for g in response.context['search_groups']}
        self.assertEqual(groups, {'phones': ['other-phone']})

        # The whole ID, as a customer would read it off the product page.
        code = Product.objects.get(slug='other-phone').catalog_code
        response = self.client.get(reverse('shop:create_product'), {'q': code.lower()})
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
        self.assertEqual(Product.objects.get(slug='charger').specifications, [['Model', 'A2305']])

        Product.objects.all().delete()
        self.assertTrue(self.post_product([]).json()['ok'])
        self.assertEqual(Product.objects.get(slug='charger').specifications, [])

    def test_characteristics_keep_the_order_they_were_entered_in(self):
        # Longest name first on purpose: jsonb sorts object keys shortest
        # first, which is what used to scramble this.
        specs = [('Встроенная память', '256 GB'), ('Модель', 'A3090'), ('CPU', 'A17'), ('Цвет', 'Black')]
        self.post_product(specs)
        product = Product.objects.get(slug='charger')

        self.assertEqual(product.spec_items, specs)
        html = self.client.get(reverse('shop:product_detail', args=[product.slug])).content.decode()
        positions = [html.index(name) for name, _value in specs]
        self.assertEqual(positions, sorted(positions))
        edit = self.client.get(reverse('shop:update_product', args=[product.id])).content.decode()
        positions = [edit.index(f'value="{name}"') for name, _value in specs]
        self.assertEqual(positions, sorted(positions))
        # The API still answers with an object, now in that same order.
        api = self.client.get(f'/api/products/{product.slug}/').json()
        self.assertEqual(list(api['specifications'].items()), specs)

    def test_characteristics_stay_editable_after_the_product_is_added(self):
        product = self.make_product('Phone', 'phone', '250.00')
        # Saved in the older object form, which still has to load.
        product.specifications = {'RAM': '8 GB', 'CPU': 'A17'}
        product.save()

        response = self.client.get(reverse('shop:update_product', args=[product.id]))
        self.assertContains(response, 'value="RAM"')
        self.assertContains(response, 'value="A17"')

        self.post_product([('CPU', 'A17 Pro'), ('Camera', '48 MP')], product=product)
        product.refresh_from_db()
        self.assertEqual(product.specifications, [['CPU', 'A17 Pro'], ['Camera', '48 MP']])

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

    def test_product_page_has_photo_arrows_only_when_there_is_a_gallery(self):
        buffer = BytesIO()
        Image.new('RGB', (10, 10), 'red').save(buffer, format='PNG')
        product = self.make_product('Phone', 'phone', '250.00')
        product.image = SimpleUploadedFile('cover.png', buffer.getvalue(), content_type='image/png')
        product.save()
        page = self.client.get(reverse('shop:product_detail', args=[product.slug]))
        self.assertNotContains(page, 'id="product-next"')

        ProductImage.objects.create(
            product=product, image=SimpleUploadedFile('two.png', buffer.getvalue(), content_type='image/png'),
        )
        page = self.client.get(reverse('shop:product_detail', args=[product.slug]))
        self.assertContains(page, 'id="product-next"')
        self.assertContains(page, 'id="product-prev"')

    def test_a_gallery_upload_that_is_not_an_image_is_refused(self):
        fake = SimpleUploadedFile('notes.png', b'<script>alert(1)</script>', content_type='image/png')
        response = self.client.post(reverse('shop:create_product'), {
            'name': 'Phone', 'slug': 'phone', 'brand': 'Example', 'category': self.category.id,
            'price': '250.00', 'description': 'A phone.', 'extra_images': [fake],
        }, **self.AJAX)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.all_objects.exists())

        buffer = BytesIO()
        Image.new('RGB', (10, 10), 'red').save(buffer, format='PNG')
        real = SimpleUploadedFile('photo.png', buffer.getvalue(), content_type='image/png')
        response = self.client.post(reverse('shop:create_product'), {
            'name': 'Phone', 'slug': 'phone', 'brand': 'Example', 'category': self.category.id,
            'price': '250.00', 'description': 'A phone.', 'extra_images': [real],
        }, **self.AJAX)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(Product.objects.get(slug='phone').gallery_images.count(), 1)

    def test_pressing_sold_twice_records_one_sale(self):
        product = self.make_product('Phone', 'phone', '250.00')

        first = self.client.post(reverse('shop:sell_product', args=[product.id]), **self.AJAX)
        second = self.client.post(reverse('shop:sell_product', args=[product.id]), **self.AJAX)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 404)
        self.assertEqual(Sale.objects.count(), 1)

    def test_sales_report_survives_an_impossible_year(self):
        for year in ('99999999', '0', '-3'):
            with self.subTest(year=year):
                response = self.client.get(reverse('shop:sales_report'), {'year': year, 'month': '1'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['selected_year'], timezone.localdate().year)

    def test_admin_can_add_edit_and_remove_extra_contacts(self):
        from .models import ExtraContact
        url = reverse('shop:manage_contacts')

        def post(rows, total=None):
            data = {'email': '', 'phone_number': '', 'whatsapp_number': '',
                    'telegram_username': '', 'instagram_username': '',
                    'extra-TOTAL_FORMS': str(total if total is not None else len(rows)),
                    'extra-INITIAL_FORMS': str(sum(1 for r in rows if r.get('id'))),
                    'extra-MIN_NUM_FORMS': '0', 'extra-MAX_NUM_FORMS': '1000'}
            for i, row in enumerate(rows):
                for key, value in row.items():
                    data[f'extra-{i}-{key}'] = value
            return self.client.post(url, data)

        # Two new rows plus a blank one, which is ignored.
        post([
            {'kind': 'whatsapp', 'label': 'Business WhatsApp', 'value': '+996 555 111 222'},
            {'kind': 'phone', 'label': '', 'value': '+996700000000'},
            {'kind': 'phone', 'label': '', 'value': ''},
        ])
        self.assertEqual(ExtraContact.objects.count(), 2)
        page = self.client.get(reverse('shop:contact_us'))
        self.assertContains(page, 'Business WhatsApp')
        self.assertContains(page, 'https://wa.me/996555111222')
        self.assertContains(page, 'tel:+996700000000')

        # A bad email is refused; delete removes a saved row.
        first, second = ExtraContact.objects.all()
        post([{'id': first.id, 'kind': 'email', 'label': '', 'value': 'nope'}])
        first.refresh_from_db()
        self.assertEqual(first.kind, 'whatsapp')
        post([
            {'id': first.id, 'kind': 'whatsapp', 'label': 'Business WhatsApp', 'value': '996555111222', 'DELETE': 'on'},
            {'id': second.id, 'kind': 'phone', 'label': '', 'value': '+996700000000'},
        ])
        self.assertEqual(list(ExtraContact.objects.all()), [second])

    def test_prices_are_whole_numbers_everywhere(self):
        product = self.make_product('Phone', 'phone', '250')
        page = self.client.get(reverse('shop:product_detail', args=[product.slug]))
        self.assertContains(page, '250')
        self.assertNotContains(page, '250.00')
        self.assertNotContains(page, '250,00')

        # The product form refuses a price with decimals, and takes a whole one.
        data = {'name': 'Tablet', 'slug': 'tablet', 'brand': 'Example', 'category': self.category.id,
                'description': 'A tablet.'}
        refused = self.client.post(reverse('shop:create_product'), {**data, 'price': '99.5'}, **self.AJAX)
        self.assertEqual(refused.status_code, 400)
        accepted = self.client.post(reverse('shop:create_product'), {**data, 'price': '99'}, **self.AJAX)
        self.assertTrue(accepted.json()['ok'])

        # Sales and the report carry whole numbers too.
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        report = self.client.get(reverse('shop:sales_report'))
        self.assertContains(report, '250')
        self.assertNotContains(report, '250,00')
        self.assertNotContains(report, '250.00')

    def test_sales_report_periods(self):
        for name, slug in (('Phone', 'phone'), ('Tablet', 'tablet'), ('Old', 'old')):
            product = self.make_product(name, slug, '100.00')
            self.client.post(reverse('shop:sell_product', args=[product.id]))
        # Push one sale four months back.
        old = Sale.objects.get(product_name='Old')
        Sale.objects.filter(pk=old.pk).update(sold_at=timezone.now() - timedelta(days=125))
        url = reverse('shop:sales_report')

        def count(**params):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 200)
            return response.context['total_count']

        self.assertEqual(count(period='month'), 2)
        self.assertEqual(count(period='last1'), 2)
        self.assertEqual(count(period='last3'), 2)
        self.assertEqual(count(period='last6'), 3)
        self.assertEqual(count(period='all'), 3)
        year = self.client.get(url, {'period': 'year', 'year': timezone.localdate().year})
        self.assertGreaterEqual(year.context['total_count'], 2)
        self.assertTrue(len(year.context['by_month']) >= 1)
        # An unknown period falls back to the current month.
        self.assertEqual(self.client.get(url, {'period': 'bogus'}).context['period'], 'month')

    def test_sales_count_towards_the_month_in_bishkek_time(self):
        product = self.make_product('Phone', 'phone', '250.00')
        self.client.post(reverse('shop:sell_product', args=[product.id]))
        sale = Sale.objects.get()
        # 1 March 03:00 in Bishkek is still 28/29 February in UTC.
        Sale.objects.filter(pk=sale.pk).update(sold_at=datetime(2026, 2, 28, 21, 0, tzinfo=dt_timezone.utc))

        march = self.client.get(reverse('shop:sales_report'), {'year': '2026', 'month': '3'})
        self.assertEqual(march.context['total_count'], 1)
        february = self.client.get(reverse('shop:sales_report'), {'year': '2026', 'month': '2'})
        self.assertEqual(february.context['total_count'], 0)

    # --- product IDs ----------------------------------------------------

    def post_category(self, **fields):
        data = {'name': 'Laptops', 'slug': '', 'id_prefix': 'L', 'id_digits': '1', 'show_newest_row': 'on'}
        data.update(fields)
        return self.client.post(reverse('shop:create_category'), data, **self.AJAX)

    def test_a_new_category_sets_its_own_id_prefix_and_products_are_numbered_from_1(self):
        self.assertTrue(self.post_category(id_prefix='a1', id_digits='3').json()['ok'])
        laptops = Category.objects.get(name='Laptops')
        self.assertEqual((laptops.id_prefix, laptops.id_digits), ('A1', 3))

        response = self.client.post(reverse('shop:create_product'), {
            'name': 'ThinkPad', 'slug': '', 'brand': 'Lenovo', 'category': laptops.id,
            'price': '900.00', 'description': 'A laptop.',
        }, **self.AJAX)
        product = Product.objects.get(name='ThinkPad')
        self.assertEqual(product.catalog_code, 'A1-001')
        # The admin sees the new ID straight away.
        self.assertIn('A1-001', response.json()['messages'][0]['text'])

    def test_an_id_prefix_must_be_letters_and_digits_and_unique(self):
        self.category.id_prefix = 'P'
        self.category.save()
        for prefix in ('p', 'L-1', 'L 1', ''):
            with self.subTest(prefix=prefix):
                response = self.post_category(id_prefix=prefix)
                self.assertEqual(response.status_code, 400)
                self.assertIn('id_prefix', [e['field'] for e in response.json()['errors']])
        self.assertFalse(Category.objects.filter(name='Laptops').exists())

    def test_a_category_can_be_edited_later_and_its_ids_follow(self):
        product = self.make_product('Phone', 'phone', '250.00')
        url = reverse('shop:edit_category', args=[self.category.id])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'value="{self.category.id_prefix}"')

        response = self.client.post(url, {
            'name': 'Phones', 'name_ru': 'Телефоны', 'slug': 'phones', 'id_prefix': 'T', 'id_digits': '2',
            'show_newest_row': 'on',
        }, **self.AJAX)
        self.assertEqual(response.json(), {'ok': True, 'messages': [], 'redirect': reverse('shop:create_category')})
        self.category.refresh_from_db()
        self.assertEqual((self.category.name_ru, self.category.id_prefix), ('Телефоны', 'T'))
        product.refresh_from_db()
        self.assertEqual(product.catalog_code, 'T-01')
        # The list it returns to says so, and links back to the editor.
        listing = self.client.get(reverse('shop:create_category'))
        self.assertContains(listing, 'saved')
        self.assertContains(listing, url)

    def test_a_category_can_keep_its_own_prefix_when_edited(self):
        url = reverse('shop:edit_category', args=[self.category.id])
        response = self.client.post(url, {
            'name': 'Phones', 'slug': 'phones', 'id_prefix': self.category.id_prefix.lower(), 'id_digits': '1',
        }, **self.AJAX)
        self.assertTrue(response.json()['ok'])

    def test_removed_page_finds_a_listing_by_its_full_id(self):
        product = self.make_product('Phone', 'phone', '250.00')
        other = self.make_product('Other', 'other', '250.00')
        self.client.post(reverse('shop:remove_product', args=[product.id]))
        self.client.post(reverse('shop:remove_product', args=[other.id]))

        response = self.client.get(reverse('shop:removed_products'), {'search': product.catalog_code})
        self.assertEqual([p.pk for p in response.context['removed_products']], [product.pk])

    def test_category_actions_in_the_background_hand_back_the_row(self):
        response = self.client.post(reverse('shop:create_category'), {'name': 'Laptops', 'slug': 'laptops', 'id_prefix': 'L', 'id_digits': '1'}, **self.AJAX)

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

    # --- the panel's menu: section cards, Back links ---------------------

    SECTION_PAGES = [
        ('shop:manage_homepage', 'homepage'),
        ('shop:manage_about', 'about'),
        ('shop:manage_contacts', 'contacts'),
        ('shop:create_product', 'products'),
        ('shop:create_category', 'categories'),
        ('shop:deleted_products', 'deleted'),
        ('shop:sales_report', 'sales'),
        ('shop:sold_products', 'sold'),
        ('shop:manage_languages', 'languages'),
    ]

    # The navbar's Settings link points at the front door too, so the Back
    # link is told apart by its chevron.
    BACK_LINK = r'<a href="/management/"[^>]*>\s*<i class="fa-solid fa-chevron-left'

    def test_the_front_door_is_the_only_menu_and_it_can_sign_out(self):
        response = self.client.get(reverse('shop:management_home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('active', response.context)

        # One card per section, in this order, and nothing else to keep in step.
        keys = [item['key'] for group in response.context['management_groups'] for item in group['items']]
        self.assertEqual(keys, [key for _name, key in self.SECTION_PAGES])
        for name, _key in self.SECTION_PAGES:
            self.assertContains(response, f'href="{reverse(name)}"')

        # Signing out lives here, as a full page post rather than a background one.
        self.assertContains(response, f'action="{reverse("admin:logout")}" data-reload')
        # No Back link on the front door itself.
        self.assertNotRegex(response.content.decode(), self.BACK_LINK)

    def test_every_section_page_has_a_back_link_and_no_sidebar(self):
        for name, key in self.SECTION_PAGES + [('shop:sales_report', 'sales')]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['active'], key)
                self.assertRegex(response.content.decode(), self.BACK_LINK)
                # The section list is not repeated beside the page.
                self.assertNotIn('management_groups', response.context)
                self.assertNotContains(response, 'id="section-menu"')

    def test_management_home_requires_a_manager(self):
        self.client.logout()
        response = self.client.get(reverse('shop:management_home'))
        self.assertEqual(response.status_code, 302)

    def test_sold_and_deleted_are_separate_panels_without_counts_on_the_front_door(self):
        sold = self.make_product('Sold Phone', 'sold-phone', '250.00')
        gone = self.make_product('Gone', 'gone', '100.00')
        self.client.post(reverse('shop:sell_product', args=[sold.id]))
        self.client.post(reverse('shop:remove_product', args=[gone.id]))

        panel = self.client.get(reverse('shop:management_home'))
        items = {item['key']: item for group in panel.context['management_groups']
                 for item in group['items']}
        self.assertNotIn('removed', items)
        # The counts are only visible once inside a section.
        self.assertNotIn('badge', items['sold'])
        self.assertNotIn('badge', items['deleted'])

        sold_page = self.client.get(reverse('shop:sold_products'))
        self.assertEqual([p.pk for p in sold_page.context['removed_products']], [sold.pk])
        deleted_page = self.client.get(reverse('shop:deleted_products'))
        self.assertEqual([p.pk for p in deleted_page.context['removed_products']], [gone.pk])
        self.assertEqual(deleted_page.context['panel_total'], 1)

        # Restoring from a panel comes back to that panel.
        response = self.client.post(reverse('shop:restore_product', args=[sold.id]), {'next': 'sold'})
        self.assertRedirects(response, reverse('shop:sold_products'))

        # The storefront renders no panel menu, so it must not pay for the count.
        self.assertNotIn('management_groups', self.client.get(reverse('shop:home')).context)

    def test_panel_inputs_are_light_not_the_old_dark_theme(self):
        for name in ('shop:manage_contacts', 'shop:manage_about', 'shop:manage_homepage'):
            with self.subTest(page=name):
                self.assertNotContains(self.client.get(reverse(name)), 'bg-slate-800')
        self.assertNotContains(self.client.get(reverse('shop:create_product'), {'action': 'new'}), 'bg-slate-800')

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
        in_language(self.client, 'ru')
        response = self.client.get(reverse('shop:manage_homepage'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Блоки главной страницы')
        self.assertContains(response, 'Управление')  # the Back link
        self.assertContains(self.client.get(reverse('shop:management_home')), 'Удалено')

    def test_regular_user_cannot_edit_the_homepage(self):
        self.client.force_login(User.objects.create_user(username='shopper', password='shopper-pass-123'))

        response = self.client.get(reverse('shop:manage_homepage'))

        self.assertRedirects(response, reverse('shop:product_list'))

    # --- removed listings ----------------------------------------------

    def test_sold_and_deleted_panels_open_on_category_cards(self):
        phones = self.category
        laptops = Category.objects.create(name='Laptops', slug='laptops', id_prefix='L')
        Category.objects.create(name='Empty', slug='empty', id_prefix='E')
        sold = self.make_product('Sold Phone', 'sold-phone', '250.00')
        gone = self.make_product('Gone Laptop', 'gone-laptop', '900.00')
        gone.category = laptops
        gone.save()
        self.client.post(reverse('shop:sell_product', args=[sold.id]))
        self.client.post(reverse('shop:remove_product', args=[gone.id]))

        # No Sold/Deleted switch left, and a card per category plus an overall one.
        page = self.client.get(reverse('shop:sold_products'))
        self.assertTrue(page.context['show_cards'])
        self.assertEqual(page.context['panel_total'], 1)
        counts = {c['category'].slug: c['count'] for c in page.context['category_cards']}
        self.assertEqual(counts, {phones.slug: 1, 'laptops': 0, 'empty': 0})
        self.assertNotContains(page, reverse('shop:deleted_products'))

        # A category card lists only that category's sold products.
        listed = self.client.get(reverse('shop:sold_products'), {'category': phones.slug})
        self.assertFalse(listed.context['show_cards'])
        self.assertEqual([p.pk for p in listed.context['removed_products']], [sold.pk])
        empty = self.client.get(reverse('shop:sold_products'), {'category': 'laptops'})
        self.assertEqual(list(empty.context['removed_products']), [])

        # The overall card lists them all; the Deleted panel never shows a sale.
        overall = self.client.get(reverse('shop:deleted_products'), {'category': 'all'})
        self.assertEqual([p.pk for p in overall.context['removed_products']], [gone.pk])

        # Restoring from a category comes back to that category.
        response = self.client.post(
            reverse('shop:restore_product', args=[sold.id]), {'next': 'sold', 'category': phones.slug}
        )
        self.assertRedirects(response, f"{reverse('shop:sold_products')}?category={phones.slug}")

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

    def test_report_opens_on_this_month_and_filters_by_category(self):
        phones = self.category
        laptops = Category.objects.create(name='Laptops', slug='laptops', id_prefix='L')
        phone = self.make_product('Galaxy Phone', 'galaxy', '250.00')
        laptop = self.make_product('Laptop', 'laptop', '900.00')
        laptop.category = laptops
        laptop.save()
        self.client.post(reverse('shop:sell_product', args=[phone.id]))
        self.client.post(reverse('shop:sell_product', args=[laptop.id]))
        url = reverse('shop:sales_report')

        # Opened bare: this month, every category, with the figures already there.
        bare = self.client.get(url)
        self.assertEqual(bare.context['period'], 'month')
        self.assertEqual(bare.context['total_revenue'], Decimal('1150.00'))
        self.assertEqual(bare.context['total_count'], 2)
        self.assertEqual(bare.context['average_sale'], Decimal('575.00'))
        self.assertEqual(sorted(bare.context['category_choices']), sorted([phones.name, 'Laptops']))
        shares = {r['category_name']: r['share'] for r in bare.context['by_category']}
        self.assertEqual(shares, {'Laptops': 78, phones.name: 22})

        # One category over a longer period.
        response = self.client.get(url, {'period': 'last3', 'category': 'Laptops'})
        self.assertEqual(response.context['total_count'], 1)
        self.assertEqual(response.context['total_revenue'], Decimal('900.00'))
        self.assertEqual([r['category_name'] for r in response.context['by_category']], ['Laptops'])

        # Brand, model and search are no longer filters.
        ignored = self.client.get(url, {'period': 'all', 'search': 'galaxy', 'brand': 'Nope'})
        self.assertEqual(ignored.context['total_count'], 2)

        # An empty period still renders, with a plain message.
        empty = self.client.get(url, {'period': 'month', 'year': 2001, 'month': 1})
        self.assertEqual(empty.context['total_count'], 0)
        self.assertEqual(empty.context['average_sale'], 0)
        self.assertContains(empty, 'Nothing was sold in this period.')

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
