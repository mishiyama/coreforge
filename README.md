# CoreForge

A Django 6.1 e-commerce storefront for PC components, with a catalogue,
cart, wishlist, checkout, reviews and analytics.

## Features

- Product catalogue with categories, search, filtering and pagination
- Cart and wishlist
- Orders with checkout and order history
- User accounts with profile management
- Reviews and ratings
- Product recommendations
- Analytics dashboard
- eSewa ePay v2 (sandbox) payment integration

## Stack

| Component | Version |
| --- | --- |
| Python | 3.12 |
| Django | 6.1 |
| Database | PostgreSQL or SQLite for local dev |
| Static files | WhiteNoise with a hashed manifest |
| Media storage | Local filesystem, or S3-compatible bucket via django-storages |
| WSGI server | Gunicorn |
| Hosting | Render (free web service) |

## Project layout

```
accounts/     registration, login, profile
analytics/    sales and product analytics
cart/         shopping cart
config/       Django project settings, URLs, WSGI/ASGI, storage backends
dashboard/    user dashboard
orders/       checkout and order processing
payments/     eSewa ePay integration
products/     catalogue, categories, import commands
recommendations/ product recommendation engine
reviews/      product reviews and ratings
wishlist/     saved products
static/       CSS, JavaScript, images and catalogue product images
templates/    HTML templates
```

## Local development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # optional; sensible defaults are built in
python manage.py migrate
python manage.py runserver
```

The app falls back to a local SQLite database when `DATABASE_URL` is unset, so
it runs with no external services.

### Importing the product catalogue

`pc-components.csv` holds the catalogue data and `static/products/` holds the
matching images:

```bash
python manage.py seed_catalog
```

`seed_catalog` imports the catalogue only when no active products exist, so it
is safe to run on every deploy. Use `--force` to re-import regardless.

The underlying command can also be run directly for finer control:

```bash
python manage.py import_pc_components pc-components.csv --images-dir static/products
```

Useful flags:

- `--dry-run` — report what would change without writing to the database
- `--replace` — deactivate the existing catalogue before importing
- `--default-stock N` — stock for rows without a stock value

## Deployment

### 1. Database

Use a PostgreSQL database. Any managed Postgres works; pick a provider whose
free tier does not expire. Render's own free Postgres instances are deleted
after 30 days, so they are not suitable for a permanent deployment.

1. Create a database and a branch.
2. Copy the connection string, for example
   `postgresql://user:password@host:5432/dbname?sslmode=require`.
3. Keep it for the next step.

### 2. Render web service

The repository includes a [`render.yaml`](render.yaml) blueprint, so you can
create the service from the Render dashboard:

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint**, select the repository, branch `main`,
   and apply.
3. Render prompts for the one value marked `sync: false`:
   - `DATABASE_URL` — the PostgreSQL connection string from step 1
4. Deploy. The build installs dependencies, collects static files, applies
   migrations and seeds the catalogue.

Everything else is already set by the blueprint. You can also create the
service manually with **New → Web Service**:

- **Build command:** `bash build.sh`
- **Start command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --worker-class gthread --threads 4 --timeout 120`
- **Health check path:** `/healthz/`
- **Python version:** 3.12.11 (set via `.python-version` and `PYTHON_VERSION`)

Migrations run inside the build command on purpose: Render only supports a
pre-deploy command on **paid** web services, so a blueprint pinned to the free
plan would otherwise start against an empty database.

The service URL looks like `https://coreforge.onrender.com`. The blueprint
already allows `*.onrender.com` hosts and CSRF origins, so no further change is
needed unless you attach a custom domain — add the domain to both
`DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` if you do.

### 3. Environment variables

The blueprint sets these, so you normally do not need to touch them:

| Variable | Value | Description |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | generated | Render generates a random secret on every apply |
| `DJANGO_DEBUG` | `False` | Must be `False` in production |
| `DATABASE_URL` | prompted | PostgreSQL connection string |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` | Comma-separated host list |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` | Comma-separated origins |

With `DJANGO_DEBUG=False` the app refuses to start unless `DATABASE_URL` is
set and `DJANGO_SECRET_KEY` is not the bundled development default, so a
misconfigured deploy fails loudly instead of silently writing to an ephemeral
SQLite file.

Add these in the Render dashboard only if you need them:

| Variable | Description |
| --- | --- |
| `ESEWA_SECRET_KEY` | eSewa ePay v2 secret key; defaults to the sandbox key |
| `ESEWA_PRODUCT_CODE` | eSewa product code; defaults to `EPAYTEST` (sandbox) |
| `AWS_STORAGE_BUCKET_NAME` and friends | Enables S3 media storage, see section 4 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Outbound email relay |
| `DEFAULT_FROM_EMAIL` | Sender address for outgoing email |

### 4. Media storage

Render's free tier has an ephemeral filesystem, so images uploaded at runtime
(profile pictures, admin product uploads) are lost on each redeploy. The
catalogue images ship with the repository as static assets and are unaffected.

To persist uploads, point the `AWS_*` variables at an S3-compatible bucket
(Cloudflare R2, Backblaze B2, MinIO):

| Variable | Description |
| --- | --- |
| `AWS_STORAGE_BUCKET_NAME` | Bucket name; enables the S3 storage backend |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials |
| `AWS_S3_ENDPOINT_URL` | Endpoint URL for R2/B2/MinIO |
| `AWS_S3_CUSTOM_DOMAIN` | Public domain for the bucket, if any |
| `AWS_STORAGE_REGION_NAME` | Region, `auto` for R2 |
| `AWS_S3_ADDRESSING_STYLE` | `path` for most non-AWS providers |

When no bucket is configured, media is served from the local filesystem.

## Free tier limitations

- The service spins down after 15 minutes without traffic and takes about a
  minute to start again on the next request.
- 512 MB RAM and 0.1 CPU. The start command uses a single Gunicorn worker with
  threads, which matches the recommended concurrency for this plan.
- Runtime uploads are lost on redeploy unless object storage is configured.
- Render's free Postgres instances are deleted after 30 days, so an external
  database is recommended.
- Pre-deploy commands are not available on free web services, so migrations
  run during the build. A build that fails to migrate aborts the deploy.

## License

Released under the MIT License. See [LICENSE](LICENSE).
