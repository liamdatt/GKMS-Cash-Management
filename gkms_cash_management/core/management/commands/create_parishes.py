from django.core.management.base import BaseCommand
from core.models import Location
from django.db import transaction

class Command(BaseCommand):
    help = 'Creates the 14 parishes of Jamaica as locations in the database'

    def handle(self, *args, **options):
        parishes = [
            {
                'name': 'Kingston',
                'address': 'Kingston, Jamaica',
            },
            {
                'name': 'St. Andrew',
                'address': 'St. Andrew, Jamaica',
            },
            {
                'name': 'St. Catherine',
                'address': 'St. Catherine, Jamaica',
            },
            {
                'name': 'Clarendon',
                'address': 'Clarendon, Jamaica',
            },
            {
                'name': 'Manchester',
                'address': 'Manchester, Jamaica',
            },
            {
                'name': 'St. Elizabeth',
                'address': 'St. Elizabeth, Jamaica',
            },
            {
                'name': 'Westmoreland',
                'address': 'Westmoreland, Jamaica',
            },
            {
                'name': 'Hanover',
                'address': 'Hanover, Jamaica',
            },
            {
                'name': 'St. James',
                'address': 'St. James, Jamaica',
            },
            {
                'name': 'Trelawny',
                'address': 'Trelawny, Jamaica',
            },
            {
                'name': 'St. Ann',
                'address': 'St. Ann, Jamaica',
            },
            {
                'name': 'St. Mary',
                'address': 'St. Mary, Jamaica',
            },
            {
                'name': 'Portland',
                'address': 'Portland, Jamaica',
            },
            {
                'name': 'St. Thomas',
                'address': 'St. Thomas, Jamaica',
            },
        ]

        # Use a transaction to ensure all parishes are created or none
        with transaction.atomic():
            created_count = 0
            existing_count = 0
            
            for parish_data in parishes:
                # Check if the location already exists (by name)
                location, created = Location.objects.get_or_create(
                    name=parish_data['name'],
                    defaults={'address': parish_data['address']}
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created location: {parish_data['name']}"))
                else:
                    existing_count += 1
                    self.stdout.write(self.style.WARNING(f"Location already exists: {parish_data['name']}"))
            
            # Provide a summary
            self.stdout.write(self.style.SUCCESS(
                f"Completed: Created {created_count} new locations, {existing_count} already existed."
            ))
            
            if existing_count == len(parishes):
                self.stdout.write(self.style.WARNING("All parishes already exist in the database.")) 