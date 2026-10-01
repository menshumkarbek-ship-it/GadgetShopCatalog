from rest_framework import viewsets
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows categories to be viewed.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    pagination_class = None  # A handful of categories; paging them helps nobody.


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that serves available devices and supports brand filtering.
    """
    serializer_class = ProductSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        # select_related: ProductSerializer nests the category, so without it
        # a list response fires one extra query per product.
        queryset = Product.objects.select_related('category').filter(is_sold=False)

        # Enable dynamic filtering via URL query params: e.g., /api/products/?brand=Apple
        brand = self.request.query_params.get('brand')
        if brand is not None:
            queryset = queryset.filter(brand__iexact=brand)

        return queryset