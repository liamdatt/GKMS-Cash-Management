#!/usr/bin/env bash
# exit on error
set -o errexit

# Print directory structure for debugging
echo "Current directory: $(pwd)"
ls -la

# Install dependencies
pip install -r requirements.txt

# Change to the correct directory where manage.py is located
cd gkms_cash_management

# Print directory after change for verification
echo "Changed to directory: $(pwd)"
ls -la

# Create staticfiles directory if it doesn't exist
mkdir -p staticfiles
chmod -R 755 staticfiles

# Print debug info about settings
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "Looking for settings modules:"
find . -name "settings" -type d

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Apply database migrations
echo "Applying migrations..."
python manage.py migrate
