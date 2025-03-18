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

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate
