from django.core.management.base import BaseCommand
from core.models import Location, LocationLimit
from django.db import transaction
from decimal import Decimal

class Command(BaseCommand):
    help = 'Creates default location limits for all locations'

    def handle(self, *args, **options):
        locations = Location.objects.all()
        
        if not locations.exists():
            self.stdout.write(self.style.ERROR("No locations found. Please run create_parishes first."))
            return
        
        default_limits = {
            'insurance_limit': Decimal('5000000.00'),
            'eod_vault_limit': Decimal('3000000.00'),
            'working_day_limit': Decimal('2000000.00'),
        }
        
        with transaction.atomic():
            created_count = 0
            updated_count = 0
            
            for location in locations:
                location_limit, created = LocationLimit.objects.update_or_create(
                    location=location,
                    defaults=default_limits
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created limits for location: {location.name}"))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"Updated limits for location: {location.name}"))
            
            # Provide a summary
            self.stdout.write(self.style.SUCCESS(
                f"Completed: Created {created_count} new location limits, updated {updated_count} existing limits."
            )) 