# Mobile Shop Project

A Django storefront for browsing phones, laptops, and tablets. This is a **view-only catalog**: visitors can search, filter, and inspect product specifications, but there is no cart, checkout, or customer account system. Catalog management (adding/editing products) is restricted to staff accounts via Django's own admin login.

It includes a read-only Django REST API for the catalog.

## Requirements

- Python 3.12 (pinned in `runtime.txt`; CI runs the same version)
- Docker Desktop and Docker Compose (recommended, for PostgreSQL)
- Git

## Local setup

1. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and update the values for your environment.

4. Start PostgreSQL, then apply migrations:

   ```powershell
   docker compose up -d db
   python manage.py migrate
   ```

5. Create a staff account so you can manage the catalog through the admin and the management panel:

   ```powershell
   python manage.py createsuperuser
   ```

6. Start the Django site:

   ```powershell
   python manage.py runserver
   ```

   Open <http://127.0.0.1:8000/>.

## Docker Compose

Run the full stack with:

```powershell
docker compose up --build
```

Services:

- Django storefront: <http://127.0.0.1:8000/>
- PostgreSQL on port 5432

The Django admin is mounted at `ADMIN_URL` (default `system-console/`), not `/admin/`.
This keeps the default path scanners probe from returning anything, but it is obscurity
rather than a control — any protected page still redirects to the real login URL, so treat
the admin as publicly known and rely on strong credentials.

## Styles (Tailwind)

Pages use one prebuilt stylesheet, `shop/static/shop/css/site.css`, compiled by Tailwind from the
classes in the templates (and in `shop/forms.py`, where the panel's inputs get theirs). The design
tokens (colours, radii) live in `tailwind.config.js`. After adding or changing classes, rebuild it
and commit the result:

```powershell
npm install        # once
npm run build:css
```

Deploys don't need Node — the built file is committed. CI rebuilds it and fails if the committed
copy is stale, so a class can't ship without its CSS.

Every `<select>` (and every input with a `<datalist>`) is drawn as the site's own dropdown by
`shop/static/shop/js/dropdowns.js`; the native control stays underneath for the form. Add
`data-native` to a `<select>` to keep the browser's.

## Language and time zone

The site opens in **Russian** for every visitor, whatever their browser's language; the navbar
switcher changes it and the choice is remembered for a year. Admin-entered content (product titles,
descriptions, page copy) is written per language in the panel. A blank Russian version falls back
to the main (EN tab) text; a blank Kyrgyz one falls back to the Russian first, then the main text.

### Automatic translation

Staff can write a product's title and description (or a category's name) in just one language:
after saving, the other two are translated automatically by Claude (Anthropic's AI) in the
background and appear a few seconds later. Russian or Kyrgyz typed into the main (EN) tab is
recognised and moved to its own tab. Only empty tabs, and tabs the translator filled before, are
ever written — anything staff type stays, and a machine translation they correct becomes theirs.
Brand and model names, numbers and units are kept as written. The product form lists which tabs
were machine-translated so they can be checked.

To turn it on:

1. Create an API key at <https://console.anthropic.com/> (API keys) and add billing.
2. Set `ANTHROPIC_API_KEY` in the host's environment (Render: the service's *Environment* tab).
3. Deploy. `build.sh` then runs `python manage.py translate_catalog`, which translates everything
   already in the catalog that is missing a language. It only touches empty or machine-made
   fields, so it is safe on every deploy. `--dry-run` lists what it would translate.

Without the key nothing is sent anywhere and blank languages keep falling back as described above.
The model is `claude-opus-5` by default (`TRANSLATION_MODEL` overrides it); a product costs
roughly one US cent to translate, so the first full-catalog run is about a dollar. Failures are
logged and never block a save.

Times are stored in UTC but shown — and grouped into months on the sales report — in
**Asia/Bishkek** time (`TIME_ZONE` in `config/settings.py`).

## Useful commands

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check
```

The public Django API and schema documentation are available at `/api/`, `/api/schema/`, and `/api/docs/`.

Tests also run automatically on every push and pull request to `main` (see `.github/workflows/ci.yml`),
against PostgreSQL and the Python version pinned in `runtime.txt`.

## The management panel

Staff run the store from **Settings** in the navbar (`/management/`; `/admin/` opens Products
directly). Its front page is a set of cards — Products, Categories, Removed, Sales, Homepage, About,
Contacts, and Sign Out — and each section opens on its own with a back arrow to the cards. Every
action there is posted in the background and the page updates in place; the same forms still work
as ordinary posts with scripts off.

Each product can carry its own **technical characteristics** as free name/value rows (a charger
may have just "Model", a phone CPU, RAM, cameras…, a cable none). They are edited on the product
form, kept in the order entered, and listed on the product page.

## Product IDs

Every product gets an ID the moment it is added: its category's **ID prefix**, a dash, and its
number within the category — `L-12` for the twelfth laptop, or `L-012` when the category's
**number length** is 3. Both are set when a category is created and can be changed later from the
pencil on the Categories page; prefixes are letters and digits, and each category needs its own.
A new prefix changes the IDs of that category's products (their numbers stay), while sales already
recorded keep the ID they were sold under. Customers see the ID only on a product's own page;
staff can search the Products and Removed pages by it.

## Removing products is reversible

Marking a listing **Sold** on the Products page is how a sale gets recorded: it writes a `Sale`
row (a snapshot of the name, brand, category, catalog code and price at that moment, which is what
the sales report reads) and then *soft*-deletes the product — the row and its photos are kept and
`deleted_at` is stamped instead. **Delete** does the same without recording a sale.

The listing disappears from the storefront, the catalog and the API immediately, but it stays on
the **Removed** page, where it can be restored or erased for good. Restoring it puts it back and
deletes the sale it recorded, so the month's revenue is not left inflated by a mis-click.

Because the row survives, a removed product keeps its slug and its per-category `#ID` reserved —
a replacement listing with the same name gets `-2` appended rather than colliding.

## Deploying safely

**Render auto-deploys from `main` by default**, which means a push migrates the production
database within minutes and CI finishes *alongside* the deploy rather than in front of it — a
red build does not stop the release.

To make tests an actual gate, turn off auto-deploy for the service in the Render dashboard and
add its Deploy Hook URL as a `RENDER_DEPLOY_HOOK` repository secret. The `deploy` job in
`.github/workflows/ci.yml` then fires the hook only after the tests pass, and stays skipped
(green) until you do both.

`build.sh` runs `migrate` against the production database on every deploy. There is no automatic
backup in front of it, so before shipping a migration that drops or alters a column:

1. **Take a backup.** `pg_dump "$DATABASE_URL" > backup-$(date +%F).sql`
2. **Verify it is non-empty** before relying on it: `wc -l backup-*.sql`
3. **Restore path**, if a migration goes wrong: `psql "$DATABASE_URL" < backup-YYYY-MM-DD.sql`
4. **Roll back one migration** without a full restore, when the migration is reversible:
   `python manage.py migrate shop <previous_migration_name>`

> Enable your host's own scheduled database backups as well — the commands above only help if
> someone remembers to run them. Check the retention window your plan actually provides; on free
> tiers it is often short or absent.

## Configuration

Never commit `.env`. Use `.env.example` as the template. In production, at minimum:

- `SECRET_KEY` — long and random (`python -c "import secrets; print(secrets.token_urlsafe(64))"`).
- `DEBUG=False`.
- `ALLOWED_HOSTS` — the domain(s) the site answers on. `CSRF_TRUSTED_ORIGINS` is derived from it
  unless set explicitly.
- `DATABASE_URL` — the managed Postgres connection string.
- `R2_*` — an S3-compatible bucket for uploaded images; without it uploads live on the host's disk
  and vanish on redeploy.
- `GOOGLE_SITE_VERIFICATION` — the Search Console token, if the site is verified there.

Run `python manage.py check --deploy` with those set to confirm nothing is left at a development
default.
