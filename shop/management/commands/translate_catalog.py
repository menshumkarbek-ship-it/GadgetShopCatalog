from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop import translation
from shop.models import Category, Product


class Command(BaseCommand):
    help = (
        "Fill in the missing English, Russian and Kyrgyz versions of every "
        "category name and product title/description with the automatic "
        "translator. Only empty or machine-made fields are written, so it is "
        "safe to run again; build.sh runs it on every deploy once "
        "ANTHROPIC_API_KEY is set."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would be translated; call nothing.')
        parser.add_argument('--limit', type=int, default=0, help='Stop after this many items (0 = all).')

    def handle(self, *args, dry_run=False, limit=0, **options):
        if not settings.ANTHROPIC_API_KEY and not dry_run:
            raise CommandError('ANTHROPIC_API_KEY is not set, so there is nothing to translate with.')

        pending = [
            obj
            for queryset in (Category.objects.order_by('id'), Product.all_objects.order_by('id'))
            for obj in queryset
            if translation.needs_translation(obj)
        ]
        if limit:
            pending = pending[:limit]
        self.stdout.write(f'{len(pending)} item(s) need translating.')

        done = failed = 0
        for obj in pending:
            label = f'{type(obj).__name__} {obj.pk} "{obj.name}"'
            if dry_run:
                self.stdout.write(f'  would translate {label}')
                continue
            try:
                written = translation.translate_object(obj)
            except translation.TranslationError as error:
                failed += 1
                self.stderr.write(f'  {label}: {error}')
                continue
            done += 1
            self.stdout.write(f'  {label}: {", ".join(written) or "nothing new"}')

        if not dry_run:
            style = self.style.WARNING if failed else self.style.SUCCESS
            self.stdout.write(style(f'Translated {done}; failed {failed}.'))
