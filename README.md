# CoreForge

A Django 6.1 e-commerce storefront for PC components, built on the NepCart
project by Anil Rijal (<https://github.com/Anil702429/NepCart>) and reworked
for production deployment.

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
| Database | PostgreSQL (Neon / Render Postgres) or SQLite for local dev |
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

The app falls back to a local SQLite database when neither `DATABASE_URL` nor
`NEON_DATABASE_URL` is set, so it runs with no external services.

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

Use a free PostgreSQL database. [Neon](https://neon.tech) has a free tier that
does not expire, unlike Render's free Postgres instances which are deleted
after 30 days.

1. Create a Neon project and a branch.
2. Copy the connection string, for example
   `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`.
3. Keep it for the next step.

### 2. Render web service

The repository includes a [`render.yaml`](render.yaml) blueprint, so you can
create the service from the Render dashboard:

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint**, select the repository, and apply.
3. Render will prompt for the values marked `sync: false`. Provide:
   - `DATABASE_URL` — the Neon connection string
   - `ESEWA_SECRET_KEY` and `ESEWA_PRODUCT_CODE` — eSewa credentials
   - `AWS_*` — only if you configure object storage
4. Deploy. The `preDeployCommand` applies migrations and seeds the catalogue.

You can also create the service manually:

- **Build command:** `./build.sh`
- **Start command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- **Pre-deploy command:** `python manage.py migrate --noinput && python manage.py seed_catalog`
- **Health check path:** `/healthz/`
- **Python version:** 3.12.11 (set via `.python-version`)

The service URL looks like `https://coreforge.onrender.com`. The blueprint
already allows `*.onrender.com` hosts and CSRF origins, so no further change is
needed unless you attach a custom domain.

### 3. Required environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DJANGO_DEBUG` | yes | Set to `False` in production |
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `DJANGO_ALLOWED_HOSTS` | yes | Comma-separated host list, e.g. `.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | yes | Comma-separated origins, e.g. `https://*.onrender.com` |
| `ESEWA_SECRET_KEY` | yes | eSewa ePay v2 secret key |
| `ESEWA_PRODUCT_CODE` | yes | eSewa product code (`EPAYTEST` for sandbox) |

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
- 512 MB RAM and 0.1 CPU.
- Runtime uploads are lost on redeploy unless object storage is configured.
- Render's free Postgres is deleted after 30 days, which is why Neon is
  recommended.

## Credits

Originally based on [NepCart](https://github.com/Anil702429/NepCart) by
Anil Rijal.
