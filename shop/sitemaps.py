from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Product


class StaticViewSitemap(Sitemap):
    """The storefront's fixed pages. The domain in each entry comes from the
    request that asked for the sitemap (RequestSite), so nothing here has to
    know where the site is deployed."""
    priority = 0.8
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return ['shop:home', 'shop:product_list', 'shop:about_us', 'shop:contact_us']

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    """One catalog page per category, so each is found on its own."""
    priority = 0.7
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return Category.objects.order_by('name')

    def location(self, category):
        return reverse('shop:product_list_by_category', args=[category.slug])


class ProductSitemap(Sitemap):
    """Every listing on sale. Sold and removed ones 404, so they are left out
    (the default manager already hides removed ones)."""
    priority = 0.6
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return Product.objects.filter(is_sold=False).only('slug', 'created_at').order_by('-created_at')

    def location(self, product):
        return reverse('shop:product_detail', args=[product.slug])

    def lastmod(self, product):
        return product.created_at
