import csv
from django.core.management.base import BaseCommand, CommandError
from core.models import Location # Assuming your app is named 'core'

class Command(BaseCommand):
    help = 'Imports locations from a CSV file into the Location model'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The CSV file path')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(self.style.SUCCESS(f'Starting import from {csv_file_path}'))

        # Delete all existing locations first
        self.stdout.write(self.style.WARNING('Deleting all existing locations from the database...'))
        try:
            count, _ = Location.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} existing locations.'))
        except Exception as e:
            raise CommandError(f'Error deleting existing locations: {e}')

        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as file: # utf-8-sig handles BOM
                reader = csv.DictReader(file)
                
                # Verify header
                expected_headers = ['Locations', 'EFT Name', 'Remote Services Name', 'Insurance Limit Name', 'Address']
                if not all(header in reader.fieldnames for header in expected_headers):
                    missing = [h for h in expected_headers if h not in reader.fieldnames]
                    raise CommandError(f"CSV file is missing expected headers: {', '.join(missing)}. Found headers: {', '.join(reader.fieldnames)}")

                locations_created = 0
                locations_updated = 0

                for row_num, row in enumerate(reader, start=2): # start=2 for 1-based data row numbering
                    try:
                        location_name = row.get('Locations', '').strip()
                        eft_name = row.get('EFT Name', '').strip()
                        remote_services_name = row.get('Remote Services Name', '').strip()
                        insurance_limit_name = row.get('Insurance Limit Name', '').strip()
                        address = row.get('Address', '').strip()

                        if not location_name:
                            self.stdout.write(self.style.WARNING(f'Skipping row {row_num}: Location Name is missing.'))
                            continue
                        
                        # Handle '0' or '#N/A' as empty strings for optional fields
                        eft_name = '' if eft_name in ['0', '#N/A'] else eft_name
                        remote_services_name = '' if remote_services_name in ['0', '#N/A'] else remote_services_name
                        insurance_limit_name = '' if insurance_limit_name in ['0', '#N/A'] else insurance_limit_name
                        address = '' if address == '#N/A' else address


                        location, created = Location.objects.update_or_create(
                            name=location_name,
                            defaults={
                                'eft_system_name': eft_name,
                                'remote_services_name': remote_services_name,
                                'insurance_limit_name': insurance_limit_name,
                                'address': address,
                            }
                        )

                        if created:
                            locations_created += 1
                            self.stdout.write(self.style.SUCCESS(f'Successfully created location: {location_name}'))
                        else:
                            locations_updated += 1
                            self.stdout.write(self.style.SUCCESS(f'Successfully updated location: {location_name}'))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing row {row_num} ({location_name if location_name else "N/A"}): {e}'))
                        self.stdout.write(self.style.WARNING(f'Row data: {row}'))


        except FileNotFoundError:
            raise CommandError(f'File not found: {csv_file_path}')
        except Exception as e:
            raise CommandError(f'An error occurred: {e}')

        self.stdout.write(self.style.SUCCESS(f'Import finished. {locations_created} locations created, {locations_updated} locations updated.')) 