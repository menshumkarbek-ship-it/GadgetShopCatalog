import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _
from .models import Product, Category, ContactSettings, ExtraContact, AboutPageContent, HomePageContent
from .utils import build_unique_slug

# Shared widget styling for every input in the management panel. The panel
# is light, so its inputs are too: quiet gray at rest, white with a soft
# indigo halo once focused.
LIGHT_INPUT_CLASS = (
    'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-900 '
    'placeholder-gray-400 focus:outline-none focus:bg-white focus:border-indigo-500 '
    'focus:ring-4 focus:ring-indigo-500/10 transition-all'
)
TEXT_INPUT_CLASS = LIGHT_INPUT_CLASS
TEXTAREA_CLASS = LIGHT_INPUT_CLASS
SELECT_CLASS = LIGHT_INPUT_CLASS + ' cursor-pointer'
FILE_INPUT_CLASS = (
    'text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 '
    'file:text-xs file:font-bold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer'
)

# Every translated field carries the same 'leave it blank and the base
# language shows instead' hint, worded for the kind of field it sits on.
FALLBACK_HEADING_HINT = _('Optional — falls back to the heading above if left blank')
FALLBACK_TEXT_HINT = _('Optional — falls back to the text above if left blank')
FALLBACK_LABEL_HINT = _('Optional — falls back to the label above if left blank')
# Kyrgyz falls back to Russian before the main text (utils.FALLBACK_LANGUAGES).
FALLBACK_KY_HINT = _('Optional — falls back to Russian, then to the main text, if left blank')


class KyrgyzFallbackHints:
    """Give every Kyrgyz (`*_ky`) field the hint that matches how it
    actually falls back — Russian first — instead of the Russian fields'
    'falls back to the text above'. One place, rather than per widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name.endswith('_ky') and 'placeholder' in field.widget.attrs:
                field.widget.attrs['placeholder'] = FALLBACK_KY_HINT


# ==========================================
# 📦 PRODUCT CREATION & UPDATE FORM
# ==========================================

class ProductCreateForm(KyrgyzFallbackHints, forms.ModelForm):
    slug = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': TEXT_INPUT_CLASS,
            'placeholder': _('Auto-generated if empty (e.g., iphone-15-pro-max)')
        })
    )

    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': TEXT_INPUT_CLASS,
            'placeholder': _('Describe the product, condition, and included accessories.'),
            'rows': 4,
        })
    )

    class Meta:
        model = Product
        fields = [
            'category', 'brand', 'name', 'name_ru', 'name_ky', 'slug', 'price',
            'description', 'description_ru', 'description_ky', 'image',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'brand': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Type any brand, e.g. Apple, Samsung, Anker...'), 'list': 'brand-suggestions', 'autocomplete': 'off'}),
            'name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('e.g., iPhone 15 Pro Max')}),
            'name_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the title above if left blank')}),
            'name_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the title above if left blank')}),
            'price': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': '999.99'}),
            'description_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the description above if left blank'), 'rows': 4}),
            'description_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the description above if left blank'), 'rows': 4}),
            'image': forms.FileInput(attrs={'class': FILE_INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = _('Choose a category…')

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')

        # all_objects: slug is unique across the table, so removed listings
        # still occupy their slug and must be checked against.
        qs = Product.all_objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if not slug and name:
            return build_unique_slug(name, qs, fallback_prefix='product')

        if qs.filter(slug=slug).exists():
            return build_unique_slug(slug, qs, fallback_prefix='product')

        return slug

    # Technical characteristics are free-form: a charger may list only its
    # model, a phone its CPU, RAM, storage and cameras, and a cable nothing
    # at all. The template posts them as parallel `spec_name` / `spec_value`
    # lists (one pair per row the admin added), stored in that order as
    # [name, value] pairs on Product.specifications.
    SPEC_NAME_MAX_LENGTH = 60
    SPEC_VALUE_MAX_LENGTH = 200

    def spec_rows(self):
        """The (name, value) rows to render: what was posted, or what's saved."""
        if self.is_bound:
            return list(zip(self.data.getlist('spec_name'), self.data.getlist('spec_value')))
        return self.instance.spec_items

    def clean(self):
        cleaned_data = super().clean()
        specifications, seen = [], set()
        for name, value in self.spec_rows():
            name, value = name.strip(), value.strip()
            if not name and not value:
                continue  # an empty row the admin added and never filled
            if not name:
                self.add_error(None, _('Every characteristic with a value needs a name.'))
                continue
            if not value:
                self.add_error(None, _('The characteristic “%(name)s” has no value.') % {'name': name})
                continue
            if len(name) > self.SPEC_NAME_MAX_LENGTH or len(value) > self.SPEC_VALUE_MAX_LENGTH:
                self.add_error(None, _('The characteristic “%(name)s” is too long.') % {'name': name[:40]})
                continue
            if name.casefold() in seen:
                self.add_error(None, _('The characteristic “%(name)s” is listed twice.') % {'name': name})
                continue
            seen.add(name.casefold())
            specifications.append([name, value])
        cleaned_data['specifications'] = specifications
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)
        product.specifications = self.cleaned_data['specifications']

        if commit:
            product.save()
        return product


# ==========================================
# 🏷️ CATEGORY CREATION FORM
# ==========================================

class CategoryCreateForm(KyrgyzFallbackHints, forms.ModelForm):
    # The slug sits inside a "/catalog/" prefix box in the template, so the
    # box carries the border and the field itself is bare.
    slug = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 min-w-0 bg-transparent border-0 py-3 pl-0 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-0',
            'placeholder': _('auto-filled, e.g. headphones')
        })
    )
    # Both rendered as toggle switches: the template hides the box and draws
    # a track and knob that follow :checked, so no widget classes here.
    is_featured_in_hero = forms.BooleanField(
        required=False,
        label=_("Show as a homepage announcement slide"),
        widget=forms.CheckboxInput(attrs={'class': ''})
    )
    show_newest_row = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Show a "Newest In" row for this category on the homepage'),
        widget=forms.CheckboxInput(attrs={'class': ''})
    )

    id_prefix = forms.CharField(
        max_length=10,
        label=_('ID prefix'),
        widget=forms.TextInput(attrs={
            'class': LIGHT_INPUT_CLASS + ' uppercase font-mono',
            'placeholder': _('e.g. L or A1'),
            'autocomplete': 'off', 'autocapitalize': 'characters', 'spellcheck': 'false',
        }),
    )
    id_digits = forms.TypedChoiceField(
        label=_('Number length'),
        coerce=int,
        choices=[(n, n) for n in range(1, 7)],
        initial=1,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = Category
        fields = ['name', 'name_ru', 'name_ky', 'slug', 'id_prefix', 'id_digits', 'is_featured_in_hero', 'show_newest_row']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': LIGHT_INPUT_CLASS,
                'placeholder': _('e.g., Headphones, Powerbanks, Smartwatches')
            }),
            'name_ru': forms.TextInput(attrs={'class': LIGHT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the name above if left blank')}),
            'name_ky': forms.TextInput(attrs={'class': LIGHT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the name above if left blank')}),
        }

    def clean_id_prefix(self):
        """Letters and digits only, stored upper-case, and not already used
        by another category — the prefix is what keeps IDs unique store-wide."""
        prefix = self.cleaned_data['id_prefix'].strip().upper()
        if not re.fullmatch(r'[^\W_]+', prefix):
            raise forms.ValidationError(_('Use letters and digits only, e.g. L or A1.'))
        taken = Category.objects.filter(id_prefix__iexact=prefix).exclude(pk=self.instance.pk).first()
        if taken:
            raise forms.ValidationError(
                _('“%(prefix)s” is already the prefix of %(category)s.') % {'prefix': prefix, 'category': taken.name}
            )
        return prefix

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')

        qs = Category.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if not slug and name:
            return build_unique_slug(name, qs, fallback_prefix='category')

        if qs.filter(slug=slug).exists():
            return build_unique_slug(slug, qs, fallback_prefix='category')

        return slug


# ==========================================
# ☎️ CONTACT SETTINGS FORM
# ==========================================

class ContactSettingsForm(forms.ModelForm):
    class Meta:
        model = ContactSettings
        fields = ['email', 'phone_number', 'whatsapp_number', 'telegram_username', 'instagram_username']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': _('e.g. hello@yourstore.com')
            }),
            'phone_number': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': '+996 700 123 456'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': _('996700123456 (country code, digits only)')
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': _('username, without the @')
            }),
            'instagram_username': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': _('username, without the @')
            }),
        }


class ExtraContactForm(forms.ModelForm):
    """One row of the "more contacts" list. A row left without a value is
    simply ignored rather than reported as an error."""

    class Meta:
        model = ExtraContact
        fields = ['kind', 'label', 'value']
        widgets = {
            'kind': forms.Select(attrs={'class': TEXT_INPUT_CLASS}),
            'label': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS, 'placeholder': _('Title, e.g. Business WhatsApp (optional)')
            }),
            'value': forms.TextInput(attrs={
                'class': TEXT_INPUT_CLASS, 'placeholder': _('Number, username, address or link')
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['value'].required = False

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        value = (cleaned.get('value') or '').strip()
        cleaned['value'] = value
        if not value or not kind:
            return cleaned
        if kind == 'email':
            try:
                validate_email(value)
            except ValidationError:
                self.add_error('value', _('Enter a valid email address.'))
        elif kind in ('phone', 'whatsapp') and not any(ch.isdigit() for ch in value):
            self.add_error('value', _('Enter a phone number.'))
        return cleaned


ExtraContactFormSet = forms.modelformset_factory(
    ExtraContact, form=ExtraContactForm, extra=0, can_delete=True,
)


# ==========================================
# 📖 ABOUT PAGE CONTENT FORM
# ==========================================

class AboutPageContentForm(KyrgyzFallbackHints, forms.ModelForm):
    class Meta:
        model = AboutPageContent
        fields = [
            'badge_text', 'badge_text_ru', 'badge_text_ky',
            'heading', 'heading_ru', 'heading_ky',
            'intro_text', 'intro_text_ru', 'intro_text_ky',
            'visit_heading', 'visit_heading_ru', 'visit_heading_ky',
            'visit_text', 'visit_text_ru', 'visit_text_ky',
            'store_address_line1', 'store_address_line1_ru', 'store_address_line1_ky',
            'store_address_line2', 'store_address_line2_ru', 'store_address_line2_ky',
            'opening_hours', 'opening_hours_ru', 'opening_hours_ky',
            'map_url',
            'store_image',
            'cta_heading', 'cta_heading_ru', 'cta_heading_ky',
            'cta_text', 'cta_text_ru', 'cta_text_ky',
        ]
        widgets = {
            'badge_text': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Family Owned Since 2010')}),
            'badge_text_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank')}),
            'badge_text_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank')}),

            'heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('e.g. About us')}),
            'heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),
            'heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),

            'intro_text': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Tell customers about your shop and your market...'), 'rows': 5}),
            'intro_text_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the story above if left blank'), 'rows': 5}),
            'intro_text_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the story above if left blank'), 'rows': 5}),

            'visit_heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('See It In Person')}),
            'visit_heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),
            'visit_heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),

            'visit_text': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Invite customers to visit your store in person...'), 'rows': 3}),
            'visit_text_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank'), 'rows': 3}),
            'visit_text_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank'), 'rows': 3}),

            'store_address_line1': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('e.g. 12 Main Street')}),
            'store_address_line1_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the address above if left blank')}),
            'store_address_line1_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the address above if left blank')}),

            'store_address_line2': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('e.g. Bishkek')}),
            'store_address_line2_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the address above if left blank')}),
            'store_address_line2_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the address above if left blank')}),

            'opening_hours': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': _('Mon–Sat 10:00–20:00 / Sun 11:00–18:00')}),
            'opening_hours_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': _('Optional — falls back to the hours above if left blank')}),
            'opening_hours_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': _('Optional — falls back to the hours above if left blank')}),
            'map_url': forms.URLInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': 'https://maps.app.goo.gl/…'}),

            'store_image': forms.FileInput(attrs={
                'class': FILE_INPUT_CLASS
            }),

            'cta_heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Ready to Find Your Next Device?')}),
            'cta_heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),
            'cta_heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the heading above if left blank')}),

            'cta_text': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Invite customers to browse or get in touch...'), 'rows': 3}),
            'cta_text_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank'), 'rows': 3}),
            'cta_text_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Optional — falls back to the text above if left blank'), 'rows': 3}),
        }


# ==========================================
# 🏠 HOME PAGE CONTENT FORM
# ==========================================

class HomePageContentForm(KyrgyzFallbackHints, forms.ModelForm):
    """
    Edits the two editorial bands on the homepage. Same shape as
    AboutPageContentForm: every field has a Russian and Kyrgyz twin, and the
    template shows one language at a time behind the EN/RU/KY tabs.
    """
    class Meta:
        model = HomePageContent
        fields = [
            'site_name', 'site_name_ru', 'site_name_ky',
            'promise_heading', 'promise_heading_ru', 'promise_heading_ky',
            'promise_card_heading', 'promise_card_heading_ru', 'promise_card_heading_ky',
            'promise_text', 'promise_text_ru', 'promise_text_ky',
            'promise_button_text', 'promise_button_text_ru', 'promise_button_text_ky',
            'promise_stat_label', 'promise_stat_label_ru', 'promise_stat_label_ky',
            'promise_stat_caption', 'promise_stat_caption_ru', 'promise_stat_caption_ky',
            'invite_eyebrow', 'invite_eyebrow_ru', 'invite_eyebrow_ky',
            'invite_heading', 'invite_heading_ru', 'invite_heading_ky',
            'invite_text', 'invite_text_ru', 'invite_text_ky',
            'invite_button_text', 'invite_button_text_ru', 'invite_button_text_ky',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('e.g. My Store')}),
            'site_name_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the name above if left blank')}),
            'site_name_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Optional — falls back to the name above if left blank')}),

            'promise_heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Why shop here')}),
            'promise_heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),
            'promise_heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),

            'promise_card_heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Checked devices at the price on the tag')}),
            'promise_card_heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),
            'promise_card_heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),

            'promise_text': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('What customers get by buying from you...'), 'rows': 4}),
            'promise_text_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': FALLBACK_TEXT_HINT, 'rows': 4}),
            'promise_text_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': FALLBACK_TEXT_HINT, 'rows': 4}),

            'promise_button_text': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Browse the catalog')}),
            'promise_button_text_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
            'promise_button_text_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),

            'promise_stat_label': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('devices in stock')}),
            'promise_stat_label_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
            'promise_stat_label_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),

            'promise_stat_caption': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Restocked every week')}),
            'promise_stat_caption_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
            'promise_stat_caption_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),

            'invite_eyebrow': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Looking for something else')}),
            'invite_eyebrow_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
            'invite_eyebrow_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),

            'invite_heading': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Not in the catalog? We will bring it in')}),
            'invite_heading_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),
            'invite_heading_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_HEADING_HINT}),

            'invite_text': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': _('Invite customers to ask for a model you do not stock yet...'), 'rows': 4}),
            'invite_text_ru': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': FALLBACK_TEXT_HINT, 'rows': 4}),
            'invite_text_ky': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'placeholder': FALLBACK_TEXT_HINT, 'rows': 4}),

            'invite_button_text': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': _('Tell us what you need')}),
            'invite_button_text_ru': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
            'invite_button_text_ky': forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': FALLBACK_LABEL_HINT}),
        }
