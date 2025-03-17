from django.core.management.base import BaseCommand
from core.models import Location

class Command(BaseCommand):
    help = 'Creates the 14 parishes of Jamaica as locations in the system'

    def handle(self, *args, **kwargs):
        # List of all parishes in Jamaica with addresses
        parishes = [
            {
                'name': 'Kingston',
                'address': 'Downtown Kingston, Jamaica'
            },
            {
                'name': 'St. Andrew',
                'address': 'Half Way Tree, St. Andrew, Jamaica'
            },
            {
                'name': 'St. Catherine',
                'address': 'Spanish Town, St. Catherine, Jamaica'
            },
            {
                'name': 'Clarendon',
                'address': 'May Pen, Clarendon, Jamaica'
            },
            {
                'name': 'Manchester',
                'address': 'Mandeville, Manchester, Jamaica'
            },
            {
                'name': 'St. Elizabeth',
                'address': 'Santa Cruz, St. Elizabeth, Jamaica'
            },
            {
                'name': 'Westmoreland',
                'address': 'Savanna-la-Mar, Westmoreland, Jamaica'
            },
            {
                'name': 'Hanover',
                'address': 'Lucea, Hanover, Jamaica'
            },
            {
                'name': 'St. James',
                'address': 'Montego Bay, St. James, Jamaica'
            },
            {
                'name': 'Trelawny',
                'address': 'Falmouth, Trelawny, Jamaica'
            },
            {
                'name': 'St. Ann',
                'address': 'St. Ann\'s Bay, St. Ann, Jamaica'
            },
            {
                'name': 'St. Mary',
                'address': 'Port Maria, St. Mary, Jamaica'
            },
            {
                'name': 'Portland',
                'address': 'Port Antonio, Portland, Jamaica'
            },
            {
                'name': 'St. Thomas',
                'address': 'Morant Bay, St. Thomas, Jamaica'
            },
        ]

        # Track how many parishes were created
        created_count = 0
        existing_count = 0

        # Create each parish as a location
        for parish in parishes:
            # Check if location already exists
            location, created = Location.objects.get_or_create(
                name=parish['name'],
                defaults={'address': parish['address']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created location for {parish["name"]}'))
            else:
                existing_count += 1
                self.stdout.write(self.style.WARNING(f'Location for {parish["name"]} already exists'))

        # Summary message
        self.stdout.write(self.style.SUCCESS(f'=== COMPLETE: Created {created_count} new locations, {existing_count} already existed ===' )) 