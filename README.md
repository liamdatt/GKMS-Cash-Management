# GKMS Cash Management System

A Django-based cash management system for monitoring cash positions, processing end-of-day reports, and managing cash requests across multiple locations.

## Features

- End of Day (EOD) reporting with denomination breakdowns
- Cash request management
- Teller balancing
- Location-based cash position tracking
- Admin dashboard with oversight controls
- User management with location assignments

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: 
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Create a superuser: `python manage.py createsuperuser`
7. Run the development server: `python manage.py runserver`

## Usage

1. Log in with your admin credentials
2. Configure locations
3. Create users and assign them to locations
4. Users can submit EOD reports and request cash
5. Admins can approve cash requests and review EOD reports
