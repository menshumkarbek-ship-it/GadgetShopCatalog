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

Which languages exist is the owner's choice: **Settings -> Languages** switches English, Russian
and Kyrgyz on and off (at least one stays on). A language that is off leaves the visitors' switcher
and is never served; the text already written in it is kept and returns when it is switched back
on. If Russian is off, the first language still on becomes the default. With one language left the
switcher disappears.

The site's own wording (buttons, labels, messages) lives in `locale/<language>/LC_MESSAGES`. After
adding or changing text in a template or view, refresh and translate the catalogs, then compile:

```powershell
python manage.py makemessages -l ru -l ky --no-wrap
# translate any new or fuzzy entries in the two django.po files, then:
python manage.py compilemessages
```

The test suite fails if an entry is left empty or fuzzy, so a missing translation cannot ship.

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
directly). Its front page is three rows of cards — **Pages** (Homepage, About, Contacts),
**Catalog** (Products, Categories, Deleted) and **Sales** (Sales report, Sold, Sign Out) — plus a
**Site** row with Languages. Each section opens on its own with a back arrow to the cards; on a
phone Sign Out is the last card. Every action there is posted in the background and the page
updates in place; the same forms still work as ordinary posts with scripts off.

The **Sales report** shows statistics for a period (a month, a year, the last 1/2/3/6/12 months, or
all time), optionally for one category: revenue, items sold, the average sale, a share-of-revenue
breakdown by category and, for longer periods, month by month. Prices are whole numbers.

**Contacts** holds the five main channels plus any number of extra ones (a second number, a
business WhatsApp, a Facebook page...), each shown as its own tile on the public Contact page.

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
staff can search the Products, Sold and Deleted pages by it.

## Sold and Deleted are reversible

Marking a listing **Sold** on the Products page is how a sale gets recorded: it writes a `Sale`
row (a snapshot of the name, brand, category, catalog code and price at that moment, which is what
the sales report reads) and then *soft*-deletes the product — the row and its photos are kept and
`deleted_at` is stamped instead. **Delete** does the same without recording a sale.

The listing disappears from the storefront, the catalog and the API immediately. Sold listings
appear in the **Sold** panel and deleted ones in the **Deleted** panel; each opens on a card per
category (plus one for everything), and from there a listing can be restored or erased for good.
Restoring a sold listing puts it back and deletes the sale it recorded, so the month's revenue is
not left inflated by a mis-click.

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

## First run for a new owner

1. Deploy with the environment above, then create the first staff account — either set
   `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` for the
   first deploy (`build.sh` creates it once), or run `python manage.py createsuperuser`.
2. Sign in at `/<ADMIN_URL>login/` (default `/system-console/login/`); you land on the home page.
   **Settings** in the navbar opens the management panel.
3. **Site -> Languages**: switch on the languages you will write content in.
4. **Pages -> Homepage**: the store name and the two homepage text blocks. **About** and
   **Contacts**: your story, address, hours and channels. Fill every language that is switched on.
5. **Catalog -> Categories**: create the categories (each gets an ID prefix), then **Products**.

The storefront starts neutral ("My Store"); nothing in it is specific to any one shop.

## Making a clean copy to hand over

Zip the project folder by hand and you ship your `.env`, virtualenv, uploaded photos and editor
settings with it. Export only what is committed instead:

```powershell
git archive --format=zip --prefix=mobile-shop/ --output=mobile-shop-1.0.zip HEAD
```

That contains the source, migrations, translations and the built stylesheet, and nothing from
`.gitignore` (no `.env`, `venv`, `media`, `staticfiles` or `node_modules`). It also leaves out the
git history, which carries the original author's name and e-mail; hand over the repository itself
instead if the history should travel with it.
