"""
Automatic translation of staff-entered text between the site's languages.

Staff write a product's title and description (or a category's name) in any
one of English, Russian or Kyrgyz and the missing languages are filled in
by Claude. Russian or Kyrgyz typed into the main (English) tab — the one
the form opens on — is noticed and moved to its own tab.

Rules that keep staff in charge:
  * Only empty fields, and fields the translator itself filled before
    (`machine_translated`), are ever written. Anything a person typed stays.
  * A machine translation that staff edit becomes theirs from then on.
  * When staff change the text a translation came from, the machine-filled
    languages are translated again; human ones are left alone.
  * Writes are compare-and-set: a field edited while a translation was in
    flight is not overwritten.

It runs in a background thread after the save, so the admin never waits on
it and a slow reply can't hit the server's request timeout. Off unless
ANTHROPIC_API_KEY is set (settings.TRANSLATION_ENABLED); the
`translate_catalog` command fills in everything already in the catalog.
"""
import json
import logging
import threading

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction

logger = logging.getLogger(__name__)

LANGUAGES = {'en': 'English', 'ru': 'Russian', 'ky': 'Kyrgyz'}

# The translatable fields of each model. The English version is the base
# field itself (`name`); the others carry a suffix (`name_ru`, `name_ky`).
FIELDS = {
    'Product': ('name', 'description'),
    'Category': ('name',),
}

# Fields that are names: a translation identical to the base (a bare brand
# and model like "iPhone 15 Pro") is left blank, since blank already shows
# the base.
NAME_FIELDS = {'name'}

SYSTEM_PROMPT = """\
You translate the listings of an electronics shop in Kyrgyzstan between \
English (en), Russian (ru) and Kyrgyz (ky).

You receive JSON: for each field, the text staff typed into its en, ru and ky \
slots. Some slots are empty, and staff sometimes type into the wrong slot \
(for example Russian text in the en slot).

For every field, return:
- `detected`: the language each slot's text is actually written in \
("en", "ru", "ky" or "other"), or "empty" for an empty slot.
- `en`, `ru`, `ky`: the field's text in that language. Where a slot already \
holds good text in its own language, return it unchanged; otherwise translate \
from the filled slots.

Write the way a native speaker would write shop copy; Kyrgyz in Cyrillic \
script. Keep brand names, model names and numbers, units (GB, mAh, W, Hz, \
inch) and technical terms (USB-C, HDMI, OLED, Wi-Fi) exactly as written. Do \
not add, drop or embellish information. A name that is only a brand and model \
(e.g. "iPhone 15 Pro Max") stays the same in every language; in a name, \
translate only the descriptive words (e.g. "Anker Wireless Charger 15W").\
"""


class TranslationError(Exception):
    """The translation could not be obtained; nothing was written."""


def slot_name(field, lang):
    return field if lang == 'en' else f'{field}_{lang}'


def is_enabled():
    return settings.TRANSLATION_ENABLED


def _manager(model):
    # The unfiltered manager: a removed product is still translated and written.
    return model._base_manager


# ── The request ─────────────────────────────────────────────────────────────

def _schema(fields):
    slot = {'type': 'string', 'enum': ['en', 'ru', 'ky', 'other', 'empty']}
    per_field = {
        'type': 'object',
        'properties': {
            'detected': {
                'type': 'object',
                'properties': {lang: slot for lang in LANGUAGES},
                'required': list(LANGUAGES),
                'additionalProperties': False,
            },
            **{lang: {'type': 'string'} for lang in LANGUAGES},
        },
        'required': ['detected', *LANGUAGES],
        'additionalProperties': False,
    }
    return {
        'type': 'object',
        'properties': {field: per_field for field in fields},
        'required': list(fields),
        'additionalProperties': False,
    }


def request_translations(texts):
    """
    `texts` is {field: {'en': ..., 'ru': ..., 'ky': ...}} (empty strings for
    empty slots). Returns {field: {'detected': {...}, 'en': ..., 'ru': ...,
    'ky': ...}}. Raises TranslationError on any failure.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0, max_retries=2)
    try:
        response = client.beta.messages.create(
            model=settings.TRANSLATION_MODEL,
            max_tokens=16000,
            # A classifier false positive is re-run on the recommended
            # fallback model server-side instead of failing the translation.
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            # Translation of short shop copy needs little deliberation.
            output_config={
                'effort': 'low',
                'format': {'type': 'json_schema', 'schema': _schema(list(texts))},
            },
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': json.dumps(texts, ensure_ascii=False)}],
        )
    except anthropic.APIStatusError as error:
        raise TranslationError(f'Claude API error {error.status_code}: {error.message}') from error
    except anthropic.APIConnectionError as error:
        raise TranslationError(f'Could not reach the Claude API: {error}') from error

    if response.stop_reason == 'refusal':
        raise TranslationError('The translation request was declined.')
    if response.stop_reason == 'max_tokens':
        raise TranslationError('The translation was cut off.')
    text = next((block.text for block in response.content if block.type == 'text'), None)
    if text is None:
        raise TranslationError('The reply had no text.')
    try:
        return json.loads(text)
    except ValueError as error:
        raise TranslationError('The reply was not valid JSON.') from error


# ── What to translate, and writing it back ─────────────────────────────────

def _plan(obj, changed):
    """
    The fields worth sending, as {field: {'texts', 'human', 'targets'}}:
    what each slot holds, which slots a person wrote, and which slots the
    translation may fill. `changed` is the set of slots staff just edited.
    """
    machine = set(obj.machine_translated or []) - set(changed)
    plan = {}
    for field in FIELDS[type(obj).__name__]:
        raw = {lang: getattr(obj, slot_name(field, lang)) or '' for lang in LANGUAGES}
        texts = {lang: value.strip() for lang, value in raw.items()}
        human = {lang for lang, text in texts.items() if text and slot_name(field, lang) not in machine}
        if not human:
            continue  # nothing a person wrote to translate from
        source_changed = any(slot_name(field, lang) in changed for lang in human)
        targets = {
            lang for lang in LANGUAGES
            if not texts[lang] or (slot_name(field, lang) in machine and source_changed)
        }
        # Freshly typed text in the main tab may not be English, which only
        # the model can tell — worth asking about while another tab is free
        # to take it. Unchanged text isn't re-sent on every save.
        fresh_main = 'en' in human and slot_name(field, 'en') in changed and len(human) < len(LANGUAGES)
        if targets or fresh_main:
            plan[field] = {'raw': raw, 'texts': texts, 'human': human, 'targets': targets}
    return plan


def needs_translation(obj, changed=()):
    return bool(_plan(obj, set(changed)))


def translate_object(obj, changed=()):
    """
    Translate `obj`'s missing languages now, synchronously. Returns the
    slots written. Raises TranslationError if the translation failed.
    """
    changed = set(changed)
    plan = _plan(obj, changed)
    if not plan:
        return []
    result = request_translations({field: p['texts'] for field, p in plan.items()})

    writes = {}        # slot -> (expected current value, new value)
    became_human = set(changed)
    became_machine = set()
    for field, p in plan.items():
        answer = result.get(field) or {}
        raw, texts, targets = p['raw'], p['texts'], set(p['targets'])
        detected = answer.get('detected') or {}

        # Russian or Kyrgyz typed into the main tab — the one staff land on —
        # moves to its own tab (unless a person already wrote that one), and
        # the main tab gets an English translation. The Russian and Kyrgyz
        # tabs are picked on purpose and share a script, so what staff type
        # there is never second-guessed.
        actual = detected.get('en')
        if 'en' in p['human'] and actual in ('ru', 'ky'):
            targets.add('en')
            home = slot_name(field, actual)
            if actual not in p['human']:
                writes[home] = (raw[actual], texts['en'])
                became_human.add(home)
                targets.discard(actual)

        # English first: a translated name that merely repeats the base (a
        # bare brand and model) is stored blank, since blank shows the base.
        base = texts['en']
        for lang in sorted(targets, key=lambda code: code != 'en'):
            new = (answer.get(lang) or '').strip()
            if not new:
                continue
            slot = slot_name(field, lang)
            if lang == 'en':
                base = new
            elif field in NAME_FIELDS and new == base:
                new = ''
            writes[slot] = (raw[lang], new)
            if new:
                became_machine.add(slot)

    return _apply(obj, writes, became_machine, became_human)


def _apply(obj, writes, became_machine, became_human):
    """Compare-and-set each slot, then record which slots are machine-made."""
    model = type(obj)
    manager = _manager(model)
    written = []
    with transaction.atomic():
        for slot, (expected, new) in writes.items():
            if expected == new:
                continue
            if manager.filter(pk=obj.pk, **{slot: expected}).update(**{slot: new}):
                setattr(obj, slot, new)
                written.append(slot)
        row = manager.select_for_update().filter(pk=obj.pk).values_list('machine_translated', flat=True).first()
        machine = (set(row or []) - became_human) | (became_machine & set(written))
        machine = sorted(slot for slot in machine if getattr(obj, slot, ''))
        manager.filter(pk=obj.pk).update(machine_translated=machine)
        obj.machine_translated = machine
    if written and model.__name__ == 'Category':
        from .views import CATEGORIES_CACHE_KEY
        cache.delete(CATEGORIES_CACHE_KEY)
    return written


def forget_edited(obj, changed):
    """Slots staff just edited are theirs now, even with no translation to
    run (the translator is off, or there is nothing to fill)."""
    machine = [slot for slot in (obj.machine_translated or []) if slot not in set(changed)]
    if machine != list(obj.machine_translated or []):
        _manager(type(obj)).filter(pk=obj.pk).update(machine_translated=machine)
        obj.machine_translated = machine


def describe(slots):
    """Machine-made slots as staff read them: ['Title (RU)', 'Description (KY)']."""
    from django.utils.translation import gettext as _
    labels = {'name': _('Title'), 'description': _('Description')}
    described = []
    for slot in slots or []:
        field, _sep, lang = slot.partition('_')
        described.append(f"{labels.get(field, field)} ({(lang or 'en').upper()})")
    return described


# ── After a save ────────────────────────────────────────────────────────────

def schedule(obj, changed=()):
    """
    Called after staff save `obj`. Starts translating its missing languages
    in the background and returns True, or returns False when there is
    nothing to do (or the translator is off).
    """
    changed = set(changed)
    forget_edited(obj, changed)
    if not is_enabled() or not needs_translation(obj, changed):
        return False

    model, pk = type(obj), obj.pk

    def run():
        try:
            fresh = _manager(model).get(pk=pk)
            written = translate_object(fresh, changed)
            logger.info('Translated %s %s: %s', model.__name__, pk, ', '.join(written) or 'nothing new')
        except TranslationError as error:
            logger.warning('Translation of %s %s failed: %s', model.__name__, pk, error)
        except Exception:
            logger.exception('Translation of %s %s failed', model.__name__, pk)
        finally:
            if settings.TRANSLATION_IN_BACKGROUND:
                connection.close()  # this thread's own connection

    if settings.TRANSLATION_IN_BACKGROUND:
        transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())
    else:
        run()
    return True
