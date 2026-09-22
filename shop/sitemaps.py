from django.contrib.sitemaps import Sitemap
from django.urls import reverse


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
