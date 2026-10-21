#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input

# Render's free web services do not support a pre-deploy command, so schema
# migrations and the catalogue seed run as part of the build instead.
python manage.py migrate --noinput
python manage.py seed_catalog
