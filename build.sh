#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

# Fail the build if a model changed without a migration, instead of deploying
# code whose queries reference columns that do not exist yet. This only reads
# the migration files on disk, so it needs no database connection.
#
# The test suite deliberately does NOT run here: it would need permission to
# CREATE a test database, which a managed Postgres role usually lacks, and a
# failure would break every deploy. Tests gate the release from CI instead —
# see .github/workflows/ci.yml and the deploy notes in README.md.
python manage.py makemigrations --check --dry-run

python manage.py migrate

# One-time staff account bootstrap: only runs when DJANGO_SUPERUSER_USERNAME
# is set (e.g. on the very first deploy). Django's --noinput reads
# DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD from the environment. `|| true`
# keeps later deploys from failing once the account already exists — there's
# no shell access on Render's free tier to run this by hand.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi
