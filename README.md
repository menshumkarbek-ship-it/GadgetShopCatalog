<div align="center">

<img src="docs/banner.svg" alt="Mobile Shop - a multilingual electronics storefront with a full management panel" width="100%">

<br>

[![Django](https://img.shields.io/badge/Django-6.0-0C4B33?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](#-run-it-with-docker)
[![Tests](https://img.shields.io/badge/tests-100%2B_passing-2EA44F)](#-tests-and-ci)
[![Languages](https://img.shields.io/badge/languages-EN%20%7C%20RU%20%7C%20KY-7C3AED)](#-three-languages-switch-them-on-and-off)
[![License](https://img.shields.io/badge/license-commercial-orange)](LICENSE)

**A fast, view-only catalogue for phones, laptops, tablets and accessories,
plus a mobile-friendly management panel the shop owner runs on their own.**

[Features](#-features) ·
[Screenshots](#-screenshots) ·
[Quick start](#-quick-start) ·
[Deploy to Google Cloud](#-deploy-to-google-cloud-run) ·
[Configuration](#-configuration) ·
[Hand-over](#-hand-over-checklist)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🛍️ Storefront
- Hero slideshow and **"Newest In"** rows built from the catalogue itself
- Catalogue with **search, category, brand and price filters**
- Product page with a **photo viewer**: arrows, swipe, arrow keys, thumbnails
- Full **specification sheet** per product, as free name/value rows
- **Enquire** button that opens WhatsApp, Telegram, Instagram, e-mail or a call
  with the product link already in the message
- About and Contact pages, written by the owner in the panel
- SEO basics: `sitemap.xml`, `robots.txt`, Open Graph tags, clean URLs
- Read-only **REST API** with Swagger docs at `/api/docs/`

</td>
<td width="50%" valign="top">

### 🧰 Management panel
- Add products with a **cover photo and a gallery**, and **characteristics** per product
- Per-category **ID prefixes** (`L-012`, `P-7`…) assigned automatically
- **Sold** and **Deleted** panels, each a card per category - every removal is **reversible**
- **Sales report**: any month, year or rolling period, filtered by category
- Edit the **homepage, About page and contacts** in every language
- Add **any number of extra contacts** (second number, business WhatsApp, Facebook…)
- Switch **languages on and off**
- Works on a phone: the panel is a list of cards, one section at a time

</td>
</tr>
</table>

<br>

## 📸 Screenshots

### The storefront - in three languages

<table>
<tr>
<td width="33%"><img src="docs/screenshots/home-en.png" alt="Home page in English"></td>
<td width="33%"><img src="docs/screenshots/home-ru.png" alt="Home page in Russian"></td>
<td width="33%"><img src="docs/screenshots/home-ky.png" alt="Home page in Kyrgyz"></td>
</tr>
<tr align="center">
<td><sub><b>English</b></sub></td>
<td><sub><b>Русский</b> (the default)</sub></td>
<td><sub><b>Кыргызча</b></sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/screenshots/catalog.png" alt="Catalogue with filters"></td>
<td width="50%"><img src="docs/screenshots/product.png" alt="Product page with photo viewer"></td>
</tr>
<tr align="center">
<td><sub><b>Catalogue</b> - search, category, brand and price filters</sub></td>
<td><sub><b>Product page</b> - photo viewer with arrows, swipe and thumbnails</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/contact.png" alt="Contact page"></td>
<td width="50%"><img src="docs/screenshots/about.png" alt="About page"></td>
</tr>
<tr align="center">
<td><sub><b>Contact</b> - every channel the owner switches on, plus extras</sub></td>
<td><sub><b>About</b> - written by the owner, per language</sub></td>
</tr>
</table>

### The management panel

<table>
<tr>
<td width="50%"><img src="docs/screenshots/panel-menu.png" alt="Management panel menu"></td>
<td width="50%"><img src="docs/screenshots/sales-report.png" alt="Sales report"></td>
</tr>
<tr align="center">
<td><sub><b>One screen, three rows of cards</b></sub></td>
<td><sub><b>Sales report</b> - revenue, items, average sale, share by category, month by month</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/panel-product.png" alt="Product form with language tabs"></td>
<td width="50%"><img src="docs/screenshots/languages.png" alt="Language switches"></td>
</tr>
<tr align="center">
<td><sub><b>Product form</b> - EN / RU / KY tabs on every text field</sub></td>
<td><sub><b>Languages</b> - switch each one on or off</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/sold-panel.png" alt="Sold panel with a card per category"></td>
<td width="50%"><img src="docs/screenshots/contacts-panel.png" alt="Contacts editor with extra contacts"></td>
</tr>
<tr align="center">
<td><sub><b>Sold</b> - a card per category, then restore or erase</sub></td>
<td><sub><b>Contacts</b> - the five main channels plus any extras</sub></td>
</tr>
</table>

### On a phone

<table>
<tr align="center">
<td width="33%"><img src="docs/screenshots/mobile-home.png" alt="Storefront on a phone" width="240"></td>
<td width="33%"><img src="docs/screenshots/mobile-product.png" alt="Product page on a phone" width="240"></td>
<td width="33%"><img src="docs/screenshots/mobile-panel.png" alt="Management panel on a phone" width="240"></td>
</tr>
<tr align="center">
<td><sub><b>Storefront</b></sub></td>
<td><sub><b>Swipeable photos</b></sub></td>
<td><sub><b>Panel</b> - Sign Out is always last</sub></td>
</tr>
</table>

> The screenshots show a demo store ("Nova Store") with invented brands and generated product
> images. A fresh install starts neutral ("My Store").

<br>

## 🚀 Quick start

You need **Python 3.12**, **Docker** (for PostgreSQL) and **Git**.

```powershell
# 1. get the code and make a virtual environment
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 2. configure
copy .env.example .env          # then edit the values you need

# 3. start the database and build the tables
docker compose up -d db
python manage.py migrate

# 4. create the owner's account and run
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Sign in at <http://127.0.0.1:8000/system-console/login/> - you land
on the home page, and **Settings** in the navbar opens the management panel.

<details>
<summary><b>macOS / Linux</b></summary>

```bash
python3.12 -m venv venv && source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
docker compose up -d db
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

</details>

### 🐳 Run it with Docker

```powershell
docker compose up --build
```

| Service | Address |
| --- | --- |
| Storefront | <http://127.0.0.1:8000/> |
| PostgreSQL | `localhost:5432` |

The Django admin is mounted at `ADMIN_URL` (default `system-console/`), not `/admin/`. That keeps
the path scanners probe from answering, but it is obscurity rather than a control - treat the
login as publicly known and rely on strong credentials.

<br>

## 🌍 Three languages, switch them on and off

```mermaid
flowchart LR
    V([Visitor]) --> M{Language<br/>cookie set?}
    M -- no --> D[Default language<br/>Russian]
    M -- yes --> E{Is it switched<br/>on?}
    E -- yes --> L[Serve that language]
    E -- no --> D
    D --> R{Russian<br/>on?}
    R -- yes --> RU[Russian]
    R -- no --> F[First language<br/>still on]
```

- The site opens in **Russian** whatever the browser says; the navbar switcher changes it and the
  choice is remembered for a year.
- **Settings -> Languages** turns English, Russian and Kyrgyz on and off. At least one stays on.
  A language that is off leaves the switcher and is never served; what was written in it is kept
  and comes back when it is switched on again. With one language left, the switcher disappears.
- Everything the owner writes (product titles and descriptions, page copy) has an **EN / RU / KY**
  tab on the form. A blank Russian text falls back to the main (EN) text; a blank Kyrgyz one falls
  back to Russian, then the main text.
- The site's own wording (buttons, labels, messages) lives in `locale/<language>/LC_MESSAGES`.
  After changing text in a template or view:

  ```powershell
  python manage.py makemessages -l ru -l ky --no-wrap
  # translate any new or fuzzy entries in the two django.po files, then:
  python manage.py compilemessages
  ```

  The test suite fails if an entry is left empty or fuzzy, so a missing translation cannot ship.
- Times are stored in UTC but shown - and grouped into months on the sales report - in
  **Asia/Bishkek** time (`TIME_ZONE` in `config/settings.py`).

<br>

## 🧭 How the panel works

Staff run the store from **Settings** in the navbar (`/management/`).

| Row | Cards |
| --- | --- |
| **Pages** | Homepage · About Page · Contacts |
| **Catalog** | Products · Categories · Deleted |
| **Sales** | Sales report · Sold · Sign Out |
| **Site** | Languages |

Every action is posted in the background and the page updates in place; the same forms still work
as ordinary posts with scripts off.

### Selling a product is one click - and reversible

Marking a listing **Sold** writes a `Sale` row (a snapshot of the name, brand, category, ID and
price at that moment - what the report reads) and then *soft*-deletes the product: the row and
its photos are kept and `deleted_at` is stamped. **Delete** does the same without recording a sale.

The listing disappears from the storefront, the catalogue and the API at once. Sold listings are
in the **Sold** panel, deleted ones in **Deleted**; each opens on a card per category (plus one for
everything), and from there a listing can be **restored** or **erased for good**. Restoring a sold
listing also deletes the sale it recorded, so a mis-click never inflates a month's revenue.

A removed product keeps its slug and its per-category ID reserved, so a replacement with the same
name gets `-2` rather than colliding.

### Product IDs

Every product gets an ID the moment it is added: its category's **ID prefix**, a dash, and its
number within the category - `L-12` for the twelfth laptop, or `L-012` when the category's number
length is 3. Both are set when a category is created and can be changed from the pencil on the
Categories page. A new prefix changes the IDs of that category's products (their numbers stay);
sales already recorded keep the ID they were sold under.

### The sales report

One filter bar, one set of results. Pick a **period** - a month, a year, the last 1 / 2 / 3 / 6 /
12 months, or all time - and optionally a **category**. You get total revenue, items sold, the
average sale, each category's share of revenue and, for longer periods, a month-by-month list.
Prices are whole numbers.

<br>

## 🏗️ Under the hood

```mermaid
flowchart TB
    B([Browser]) -->|HTTPS| P[Reverse proxy / Cloud Run]
    P --> G[Gunicorn]
    G --> W[WhiteNoise<br/>static files]
    G --> D[Django 6]
    D --> L[Language<br/>middleware]
    L --> V[Views and templates]
    V --> DB[(PostgreSQL)]
    V --> S[(Object storage<br/>product photos)]
    V --> A[REST API<br/>read-only]
```

### Data model

```mermaid
erDiagram
    CATEGORY ||--o{ PRODUCT : contains
    PRODUCT  ||--o{ PRODUCT_IMAGE : "has gallery"
    PRODUCT  ||--o{ SALE : "recorded as"
    CATEGORY {
        string name "+ name_ru, name_ky"
        string slug
        string id_prefix
        bool   is_featured_in_hero
        bool   show_newest_row
    }
    PRODUCT {
        string brand
        string name "+ name_ru, name_ky"
        decimal price "whole number"
        json   specifications "ordered name/value pairs"
        image  image "the cover"
        int    category_number "the L-12 part"
        datetime deleted_at "null = on sale"
    }
    SALE {
        string product_name "snapshot"
        string category_name "snapshot"
        decimal price "snapshot"
        datetime sold_at
    }
```

Five **single-row settings tables** hold what the owner edits in the panel: `HomePageContent`,
`AboutPageContent`, `ContactSettings`, `LanguageSettings`, and a list of `ExtraContact` rows.

### Project layout

```text
.
├── config/                 settings, URLs, WSGI/ASGI
├── shop/
│   ├── models.py           catalogue, sales and the settings tables
│   ├── views.py            storefront and management panel
│   ├── forms.py            product / category / contact / language forms
│   ├── middleware.py       serves only the languages that are switched on
│   ├── languages.py        which languages are on (cached)
│   ├── api.py              read-only REST API
│   ├── sitemaps.py         sitemap.xml
│   ├── templates/shop/     storefront and panel templates
│   ├── static/shop/        site.css (built), dropdowns.js, icons
│   ├── migrations/
│   └── tests.py            100+ tests
├── locale/ru, locale/ky    Russian and Kyrgyz translations
├── templates/              admin login, 404, 500
├── docs/                   banner and screenshots used in this file
├── Dockerfile              production image (Gunicorn)
├── docker-compose.yml      local PostgreSQL + dev server
├── build.sh                build/deploy script for hosts that run one (Render)
└── .github/workflows/      CI: tests, stylesheet check, static build
```

### Styles (Tailwind)

Pages use one prebuilt stylesheet, `shop/static/shop/css/site.css`, compiled by Tailwind from the
classes in the templates (and in `shop/forms.py`, where the panel's inputs get theirs). The design
tokens live in `tailwind.config.js`. After adding or changing classes, rebuild it and commit it:

```powershell
npm install        # once
npm run build:css
```

Deploys don't need Node - the built file is committed. CI rebuilds it and fails if the committed
copy is stale, so a class can never ship without its CSS.

Every `<select>` is drawn as the site's own dropdown by `shop/static/shop/js/dropdowns.js`; the
native control stays underneath for the form. Add `data-native` to keep the browser's.

<br>

## 🔧 Configuration

Copy `.env.example` to `.env` for local work and **never commit it**. In production set these on
the host:

| Variable | Required | What it does |
| --- | :---: | --- |
| `SECRET_KEY` | ✅ | Long and random: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DEBUG` | ✅ | Must be `False` in production (it is the default) |
| `ALLOWED_HOSTS` | ✅ | Comma-separated domains the site answers on. `.run.app` allows every Cloud Run URL |
| `DATABASE_URL` or `DB_*` | ✅ | `DATABASE_URL` for a managed database (SSL is required); otherwise `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` |
| `R2_BUCKET_NAME` `R2_ACCESS_KEY_ID` `R2_SECRET_ACCESS_KEY` `R2_ENDPOINT_URL` | ✅ | An S3-compatible bucket for uploaded photos. Without it they sit on the server's disk and **vanish on redeploy** |
| `R2_PUBLIC_DOMAIN` | | Public domain of that bucket; leave blank to use signed URLs |
| `ADMIN_URL` | | Where the Django admin lives (default `system-console/`) |
| `CSRF_TRUSTED_ORIGINS` | | Derived from `ALLOWED_HOSTS` when blank |
| `GOOGLE_SITE_VERIFICATION` | | Search Console token, rendered as a `<meta>` tag |
| `LOG_LEVEL` | | `DEBUG` / `INFO` (default) / `WARNING` / `ERROR` |
| `DJANGO_SUPERUSER_USERNAME` `_EMAIL` `_PASSWORD` | | First deploy only: `build.sh` creates this account once |

Then confirm nothing is left at a development default:

```powershell
python manage.py check --deploy
```

With `DEBUG=False` the site redirects HTTP to HTTPS, sends HSTS, and marks the session, CSRF and
language cookies secure.

<br>

## 🚢 Deploy to Google Cloud Run

Cloud Run runs the `Dockerfile` as it is - Gunicorn on port 8000, static files already collected.
You need a Google Cloud project with billing and the [`gcloud` CLI](https://cloud.google.com/sdk/docs/install).

> **Two things to know first.** Cloud Run has no persistent disk, so uploaded photos *must* go to
> a bucket (step 2). And the app caches a few settings for 60 seconds per instance, which is fine
> for one or several instances.

Set these once so the commands below can be pasted:

```bash
PROJECT=your-project-id
REGION=europe-west1
SQL=shop-db            # Cloud SQL instance name
DB_NAME=shop
DB_USER=shop
```

**1. Enable the services and create the database**

```bash
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
    cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud sql instances create $SQL --database-version=POSTGRES_15 --tier=db-f1-micro --region=$REGION
gcloud sql databases create $DB_NAME --instance=$SQL
gcloud sql users create $DB_USER --instance=$SQL --password='CHOOSE-A-STRONG-PASSWORD'
```

**2. Photos: create a bucket**

The app talks to any S3-compatible store (the settings are named `R2_*` because it was built
against Cloudflare R2, which has a generous free tier and is the path tested end to end).

- *Cloudflare R2:* create a bucket and an API token, then use its S3 endpoint
  (`https://<account>.r2.cloudflarestorage.com`) and keys.
- *Google Cloud Storage:* it has an S3-compatible API. Create a bucket, make an HMAC key for a
  service account (`gcloud storage hmac create SERVICE_ACCOUNT_EMAIL`), and use
  `R2_ENDPOINT_URL=https://storage.googleapis.com` with that key. Upload one test photo after
  deploying to confirm it works for your bucket.

**3. Keep secrets in Secret Manager**

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))" | \
    gcloud secrets create django-secret-key --data-file=-
printf '%s' 'CHOOSE-A-STRONG-PASSWORD' | gcloud secrets create db-password --data-file=-
printf '%s' 'YOUR-BUCKET-SECRET-KEY'   | gcloud secrets create bucket-secret-key --data-file=-
```

(Give the Cloud Run service account the *Secret Manager Secret Accessor* role.)

**4. Build and deploy**

```bash
gcloud run deploy mobile-shop \
  --source . --region $REGION --port 8000 --allow-unauthenticated \
  --add-cloudsql-instances $PROJECT:$REGION:$SQL \
  --set-env-vars "DEBUG=False,ALLOWED_HOSTS=.run.app,DB_HOST=/cloudsql/$PROJECT:$REGION:$SQL,DB_NAME=$DB_NAME,DB_USER=$DB_USER,R2_BUCKET_NAME=your-bucket,R2_ENDPOINT_URL=https://your-endpoint,R2_ACCESS_KEY_ID=your-key-id" \
  --set-secrets "SECRET_KEY=django-secret-key:latest,DB_PASSWORD=db-password:latest,R2_SECRET_ACCESS_KEY=bucket-secret-key:latest"
```

`--source .` builds the image with Cloud Build from the `Dockerfile`. The database is reached over
Cloud SQL's Unix socket, which is why `DB_HOST` is a `/cloudsql/...` path (use the `DB_*`
variables here, not `DATABASE_URL`).

**5. Create the tables and the owner's account (one time)**

Cloud Run does not run `build.sh`, so run migrations as a one-off job from the image you just deployed:

```bash
IMAGE=$(gcloud run services describe mobile-shop --region $REGION \
        --format 'value(spec.template.spec.containers[0].image)')

gcloud run jobs deploy shop-migrate --image $IMAGE --region $REGION \
  --set-cloudsql-instances $PROJECT:$REGION:$SQL \
  --set-env-vars "DEBUG=False,ALLOWED_HOSTS=.run.app,DB_HOST=/cloudsql/$PROJECT:$REGION:$SQL,DB_NAME=$DB_NAME,DB_USER=$DB_USER" \
  --set-secrets "SECRET_KEY=django-secret-key:latest,DB_PASSWORD=db-password:latest" \
  --command python --args manage.py,migrate,--noinput
gcloud run jobs execute shop-migrate --region $REGION --wait

# the first staff account
gcloud run jobs deploy shop-admin --image $IMAGE --region $REGION \
  --set-cloudsql-instances $PROJECT:$REGION:$SQL \
  --set-env-vars "DEBUG=False,ALLOWED_HOSTS=.run.app,DB_HOST=/cloudsql/$PROJECT:$REGION:$SQL,DB_NAME=$DB_NAME,DB_USER=$DB_USER,DJANGO_SUPERUSER_USERNAME=owner,DJANGO_SUPERUSER_EMAIL=you@example.com" \
  --set-secrets "SECRET_KEY=django-secret-key:latest,DB_PASSWORD=db-password:latest,DJANGO_SUPERUSER_PASSWORD=owner-password:latest" \
  --command python --args manage.py,createsuperuser,--noinput
gcloud run jobs execute shop-admin --region $REGION --wait
```

(Create the `owner-password` secret the same way as in step 3.) Run the `shop-migrate` job again
after every release that adds a migration.

**6. Use your own domain**

```bash
gcloud beta run domain-mappings create --service mobile-shop --domain shop.example.com --region $REGION
```

Add the DNS records it prints, then redeploy with `ALLOWED_HOSTS=shop.example.com` (and
`CSRF_TRUSTED_ORIGINS` is derived from it).

<details>
<summary><b>Other hosts</b></summary>

- **Render:** `build.sh` installs, collects static files, checks for missing migrations, migrates
  and (once) creates the superuser. Render auto-deploys from `main`; to make the tests an actual
  gate, turn auto-deploy off and add the service's Deploy Hook as the `RENDER_DEPLOY_HOOK`
  repository secret - the `deploy` job in `.github/workflows/ci.yml` then fires it only after the
  tests pass.
- **Any Docker host:** build the `Dockerfile`, set the variables above, and run
  `python manage.py migrate` once per release.

</details>

### Before you ship a migration that drops or alters a column

`migrate` runs against the live database with no automatic backup in front of it. So:

1. **Back up:** `pg_dump "$DATABASE_URL" > backup-$(date +%F).sql`
2. **Check it is not empty:** `wc -l backup-*.sql`
3. **Restore, if it goes wrong:** `psql "$DATABASE_URL" < backup-YYYY-MM-DD.sql`
4. **Or roll back one reversible migration:** `python manage.py migrate shop <previous_migration_name>`

Also switch on your host's own scheduled database backups, and check how long your plan keeps them.

<br>

## 🧪 Tests and CI

```powershell
python manage.py check
python manage.py test            # 100+ tests
python manage.py makemigrations --check
```

On every push and pull request to `main`, GitHub Actions
([`ci.yml`](.github/workflows/ci.yml)) runs the tests against PostgreSQL on the Python version
pinned in `runtime.txt`, fails if the built stylesheet is stale or a migration is missing, and
checks that static files collect. The public API and its docs are at `/api/`, `/api/schema/` and
`/api/docs/`.

<br>

## 📦 Hand-over checklist

**For the new owner, on first run:**

1. Deploy with the variables above, then create the first staff account (see the Cloud Run step 5,
   or `python manage.py createsuperuser`).
2. Sign in at `/system-console/login/` - you land on the home page; **Settings** opens the panel.
3. **Site -> Languages:** switch on the languages you will write in.
4. **Pages -> Homepage:** the store name and the two homepage text blocks. **About** and
   **Contacts:** your story, address, hours and channels. Fill every language that is switched on.
5. **Catalog -> Categories**, then **Products**.

**For the seller, to make a clean copy:** zipping the folder by hand ships your `.env`, virtual
environment and uploaded photos. Export only what is committed instead:

```powershell
git archive --format=zip --prefix=mobile-shop/ --output=mobile-shop-1.0.zip HEAD
```

That contains the source, migrations, translations and the built stylesheet, and nothing from
`.gitignore`. It also leaves out the git history, which carries the author's name and e-mail.

<br>

## 📄 License

Commercial, single-site licence - see [`LICENSE`](LICENSE). The licence covers this code; the
open-source libraries it depends on (Django, Django REST framework, Pillow, WhiteNoise, Gunicorn,
Tailwind CSS and others) keep their own licences.

<div align="center">
<sub>Built with Django · Made for shops in Kyrgyzstan and anywhere that reads English, Russian or Kyrgyz</sub>
</div>
