from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from . import views
from . import api

app_name = 'shop'

# Register DRF viewsets with the router
router = DefaultRouter()
router.register(r'products', api.ProductViewSet, basename='api-product')
router.register(r'categories', api.CategoryViewSet, basename='api-category')

urlpatterns = [
    # --- DRF API Gateway ---
    path('api/', include(router.urls)),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='shop:schema'), name='swagger-ui'),

    # --- Home Page & Catalog Routes ---
    path('', views.home_page, name='home'),
    path('catalog/', views.product_list, name='product_list'),
    path('catalog/<slug:category_slug>/', views.product_list, name='product_list_by_category'),

    # --- Product Detail & Specs ---
    path('product/<slug:product_slug>/', views.product_detail, name='product_detail'),
    path('product/<slug:product_slug>/specs/', views.product_specs, name='product_specs'),

    # --- Catalog Management (staff/manager only) ---
    path('management/', views.management_home, name='management_home'),
    path('management/product/add/', views.create_product, name='create_product'),
    path('management/product/add/<int:product_id>/', views.create_product, name='update_product'),
    path('management/product/<int:product_id>/sold/', views.sell_product, name='sell_product'),
    path('management/product/<int:product_id>/remove/', views.remove_product, name='remove_product'),
    path('management/product/<int:product_id>/restore/', views.restore_product, name='restore_product'),
    path('management/product/<int:product_id>/purge/', views.purge_product, name='purge_product'),
    path('management/product/image/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),
    path('management/category/add/', views.create_category, name='create_category'),
    path('management/category/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('management/category/<int:category_id>/toggle-hero/', views.toggle_category_hero, name='toggle_category_hero'),
    path('management/category/<int:category_id>/toggle-newest/', views.toggle_category_newest, name='toggle_category_newest'),
    path('management/category/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('management/removed/', views.removed_products, name='removed_products'),
    path('management/sold/', views.sold_products, name='sold_products'),
    path('management/deleted/', views.deleted_products, name='deleted_products'),
    path('management/homepage/', views.manage_homepage, name='manage_homepage'),
    path('management/contacts/', views.manage_contacts, name='manage_contacts'),
    path('management/about/', views.manage_about, name='manage_about'),
    # Two views of one page: the monthly report, and the same figures
    # over every sale ever recorded.
    path('management/sales/', views.sales_report, name='sales_report'),
    path('management/archive/', views.sales_archive, name='sales_archive'),
    path('management/sales/<int:sale_id>/discard/', views.discard_sale, name='discard_sale'),

    # --- Auxiliary Pages ---
    path('pages/about-us/', views.about_us, name='about_us'),
    path('pages/contact-us/', views.contact_us, name='contact_us'),
]
