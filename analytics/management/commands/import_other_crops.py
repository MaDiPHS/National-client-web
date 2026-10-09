# analytics/management/commands/import_other_crops.py
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.models import HumanDetectedDisease, Farm
from ._csv_utils import (
    read_csv_rows, get_str, get_int, get_float,
    parse_datetime_field, parse_threats, ProgressReporter,
)


class Command(BaseCommand):
    help = 'Bulk import HumanDetectedDisease (Other Crop) records from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--batch-size', type=int, default=500)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--skip-errors', action='store_true',
            help='Skip rows that fail instead of aborting',
        )
        parser.add_argument('--stop-after-errors', type=int, default=50)

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        skip_errors = options['skip_errors']
        stop_after_errors = options['stop_after_errors']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Importing HumanDetectedDisease records from {csv_path}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN"))

        start = time.time()

        try:
            headers, rows = read_csv_rows(csv_path)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        total = len(rows)
        self.stdout.write(f"Read {total} rows.")

        self.stdout.write("Pre-loading farm lookup ...")
        farm_lookup = dict(Farm.objects.values_list('farm_id', 'id'))
        self.stdout.write(f"Loaded {len(farm_lookup)} farms.")

        self.stdout.write("Pre-loading existing OtherCrop keys ...")
        existing_keys = set(
            HumanDetectedDisease.objects.values_list(
                'record_date', 'farm_id', 'other_crops_id'
            )
        )
        existing_ids = set(
            HumanDetectedDisease.objects.values_list('other_crops_id', flat=True)
        )
        self.stdout.write(f"Found {len(existing_ids)} existing records.")

        reporter = ProgressReporter(total=total, prefix='[OtherCrop]')
        errors_log = []
        buffer = []

        def flush_buffer():
            if not buffer or dry_run:
                return
            HumanDetectedDisease.objects.bulk_create(buffer, batch_size=batch_size)
            buffer.clear()

        for idx, row in enumerate(rows, start=2):
            try:
                # other_crops_id can be missing but defaults to 0 in the model
                other_crops_id_str = get_str(row, 'other_crops_id')
                if other_crops_id_str is None:
                    other_crops_id = 0
                else:
                    try:
                        other_crops_id = int(float(other_crops_id_str))
                    except ValueError:
                        raise ValueError(f"Invalid other_crops_id '{other_crops_id_str}'")

                user_id = get_int(row, 'user_id')
                crop_name = get_str(row, 'crop_name')
                if not crop_name:
                    raise ValueError("'crop_name' is required")

                lat = get_float(row, 'lat')
                lng = get_float(row, 'lng')

                farm = None
                farm_id_str = get_str(row, 'farm_id')
                if farm_id_str is not None:
                    farm_pk = farm_lookup.get(int(float(farm_id_str)))
                    if farm_pk is None:
                        raise ValueError(f"Farm with farm_id={farm_id_str} does not exist")
                    farm = Farm(pk=farm_pk)

                # Parse date/time from collected_at -> created_at -> updated_at
                record_date = None
                collected_time = None
                created_time = None
                updated_time = None

                for field in ('collected_at', 'created_at', 'updated_at'):
                    d, t = parse_datetime_field(row.get(field))
                    if field == 'collected_at':
                        collected_time = t
                    elif field == 'created_at':
                        created_time = t
                    elif field == 'updated_at':
                        updated_time = t

                    if d is not None and record_date is None:
                        record_date = d

                if record_date is None:
                    record_date = timezone.now().date()

                # Duplicate detection
                key = (record_date, farm.pk if farm else None, other_crops_id)
                if key in existing_keys or other_crops_id in existing_ids:
                    reporter.tick('skipped')
                    continue

                obj = HumanDetectedDisease(
                    other_crops_id=other_crops_id,
                    user_id=user_id,
                    crop_name=crop_name,
                    description=get_str(row, 'description'),
                    collected_at=collected_time,
                    created_at=created_time,
                    updated_at=updated_time,
                    lat=lat,
                    lng=lng,
                    farm=farm,
                    threats=parse_threats(row.get('threats')),
                    comment=get_str(row, 'comment'),
                    infection_percentage=get_float(row, 'infection_percentage'),
                    country_code=get_str(row, 'country_code'),
                    county=get_str(row, 'county'),
                    state=get_str(row, 'state'),
                    region=get_str(row, 'region'),
                    location_name=get_str(row, 'location_name'),
                    record_date=record_date,
                    collected_date=record_date if collected_time else None,
                    created_date=timezone.now().date(),
                )

                if not dry_run:
                    buffer.append(obj)
                    if len(buffer) >= batch_size:
                        flush_buffer()

                existing_keys.add(key)
                existing_ids.add(other_crops_id)
                reporter.tick('created')

            except Exception as e:
                reporter.tick('error')
                errors_log.append(f"Row {idx}: {e}")
                if not skip_errors:
                    raise CommandError(f"Aborting. Row {idx}: {e}")
                if len(errors_log) >= stop_after_errors:
                    self.stdout.write(self.style.ERROR(
                        f"Stopping after {stop_after_errors} errors."
                    ))
                    break

        flush_buffer()
        elapsed = time.time() - start
        reporter.print_status()

        if errors_log:
            self.stdout.write(self.style.WARNING(f"\n{len(errors_log)} errors:"))
            for err in errors_log[:20]:
                self.stdout.write(f"  {err}")
            if len(errors_log) > 20:
                self.stdout.write(f"  ... and {len(errors_log) - 20} more")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone in {elapsed:.1f}s. "
            f"Created={reporter.created} Skipped={reporter.skipped} "
            f"Errors={reporter.errors}"
        ))