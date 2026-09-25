from io import BytesIO
from PIL import Image, ImageChops, ImageOps
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils.translation import get_language

# Extra languages the storefront supports beyond the default/base language
# (English). Matches settings.LANGUAGES minus 'en'. Kept as a plain tuple
# here (rather than importing settings) to avoid any import-order issues
# since this module is imported from models.py.
TRANSLATABLE_LANGUAGES = ('ru', 'ky')


# Where each language looks when its own variant is left blank, before the
# base field. Kyrgyz readers read Russian, and the site is Russian-first, so
# a listing written in Russian but not yet in Kyrgyz shows its Russian text
# on the Kyrgyz site rather than the base (English-tab) one.
FALLBACK_LANGUAGES = {
    'ky': ('ru',),
}


def translatable_property(base_field):
    """
    Build a @property for a model that returns the current-language variant
    of `base_field`. When that variant is blank it tries the language's
    fallbacks (Kyrgyz -> Russian), then the plain `base_field` value.

    Usage on a model that has `name`, `name_ru`, `name_ky` fields:
        translated_name = translatable_property('name')
    Then templates use `{{ obj.translated_name }}` instead of `{{ obj.name }}`
    wherever admin-entered content should follow the site's active language.
    """
    def getter(self):
        language = (get_language() or 'en').split('-')[0]
        if language in TRANSLATABLE_LANGUAGES:
            for candidate in (language, *FALLBACK_LANGUAGES.get(language, ())):
                value = getattr(self, f'{base_field}_{candidate}', '')
                if value:
                    return value
        return getattr(self, base_field)

    return property(getter)

# Django's slugify() strips non-ASCII characters entirely, so a Cyrillic-only
# name (Russian or Kyrgyz, both supported languages on this site) would slugify
# to an empty string. Transliterate common Cyrillic letters to Latin first so
# names like "Наушники" or "Кулактук" still produce a readable, valid slug.
CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Kyrgyz-specific letters
    'ң': 'ng', 'ө': 'o', 'ү': 'u',
}


def transliterate(text):
    result = []
    for char in text:
        lower = char.lower()
        if lower in CYRILLIC_TO_LATIN:
            replacement = CYRILLIC_TO_LATIN[lower]
            result.append(replacement.upper() if char.isupper() and replacement else replacement)
        else:
            result.append(char)
    return ''.join(result)


def process_no_bg_image(image_field_file, filename_prefix):
    """
    Strip a near-white background to transparent and crop to a square 700x700
    canvas, returning (filename, ContentFile) ready to assign to an
    ImageField via `field.save(filename, content, save=False)`.

    Shared by Product's primary image and ProductImage gallery photos so
    every product photo gets the same consistent, catalog-ready look.
    """
    img = Image.open(image_field_file)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Clear the alpha wherever all three channels are near-white. This used to
    # be a per-pixel Python loop over the full image, running synchronously
    # inside Product.save() and so inside the request — half a million
    # iterations per upload. These band operations produce the same result
    # entirely in Pillow's C layer. `point()` builds a 256-entry lookup table
    # rather than calling the lambda per pixel, and `darker` (per-pixel min)
    # acts as a logical AND across the three 0/255 masks.
    red, green, blue, alpha = img.split()
    to_mask = lambda band: band.point(lambda value: 255 if value > 240 else 0)
    near_white = ImageChops.darker(ImageChops.darker(to_mask(red), to_mask(green)), to_mask(blue))
    img.putalpha(ImageChops.subtract(alpha, near_white))

    canvas_size = (700, 700)
    cropped_img = ImageOps.fit(img, canvas_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

    buffer = BytesIO()
    cropped_img.save(buffer, format='PNG')
    buffer.seek(0)

    filename = f"{filename_prefix}_nobg.png"
    return filename, ContentFile(buffer.read())


def derive_id_prefix(name, taken, max_length=10):
    """
    A product-ID prefix for a category that wasn't given one: the first six
    letters/digits of its name, upper-cased ('Phones' -> 'PHONES') — the form
    IDs took before prefixes could be set — made unique against `taken` by
    appending 2, 3, …
    """
    base = ''.join(ch for ch in name.upper() if ch.isalnum())[:6] or 'ITEM'
    taken = {prefix.upper() for prefix in taken}
    prefix, suffix = base, 2
    while prefix in taken:
        tail = str(suffix)
        prefix = base[:max_length - len(tail)] + tail
        suffix += 1
    return prefix


def build_unique_slug(name, queryset, fallback_prefix='item'):
    """Slugify `name` (transliterating Cyrillic first so it never comes back
    empty), then make it unique against `queryset` by appending -2, -3, etc."""
    base_slug = slugify(transliterate(name)) or f"{fallback_prefix}-{queryset.count() + 1}"

    slug = base_slug
    suffix = 2
    while queryset.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug
