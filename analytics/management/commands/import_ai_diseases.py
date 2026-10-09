# analytics/management/commands/import_ai_diseases.py
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.models import AIDisease, Farm
from ._csv_utils import (
    read_csv_rows, get_str, get_int, get_float,
    parse_datetime_field, ProgressReporter,
)


class Command(BaseCommand):
    help = 'Bulk import AIDisease records from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='Commit every N rows (default: 500)',
        )
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--skip-duplicates', action='store_true', default=True,
            help='Skip duplicate records (default: True)',
        )
        parser.add_argument(
            '--skip-errors', action='store_true',
            help='Skip rows that fail instead of aborting',
        )
        parser.add_argument(
            '--stop-after-errors', type=int, default=50,
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        skip_errors = options['skip_errors']
        stop_after_errors = options['stop_after_errors']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Importing AIDisease records from {csv_path}"
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

        # Prefetch farm lookup table so we don't hit the DB for every row
        self.stdout.write("Pre-loading farm lookup ...")
        farm_lookup = dict(Farm.objects.values_list('farm_id', 'id'))
        self.stdout.write(f"Loaded {len(farm_lookup)} farms.")

        # Prefetch existing disease IDs to skip duplicates fast
        self.stdout.write("Pre-loading existing AIDisease keys ...")
        existing_keys = set(
            AIDisease.objects.values_list('record_date', 'farm_id', 'ai_disease_id')
        )
        existing_ids = set(
            AIDisease.objects.values_list('ai_disease_id', flat=True)
        )
        self.stdout.write(f"Found {len(existing_ids)} existing records.")

        reporter = ProgressReporter(total=total, prefix='[AIDisease]')
        errors_log = []

        # Buffer for bulk_create
        buffer = []

        def flush_buffer():
            if not buffer or dry_run:
                return
            AIDisease.objects.bulk_create(buffer, batch_size=batch_size)
            buffer.clear()

        for idx, row in enumerate(rows, start=2):
            try:
                ai_disease_id = get_int(row, 'ai_disease_id')
                user_id = get_int(row, 'user_id', required=False)
                crop_name = get_str(row, 'crop_name')
                if not crop_name:
                    raise ValueError("'crop_name' is required")

                lat = get_float(row, 'lat')
                lng = get_float(row, 'lng')

                # Farm FK
                farm = None
                farm_id_str = get_str(row, 'farm_id')
                if farm_id_str is not None:
                    farm_pk = farm_lookup.get(int(float(farm_id_str)))
                    if farm_pk is None:
                        raise ValueError(f"Farm with farm_id={farm_id_str} does not exist")
                    farm = Farm(pk=farm_pk)

                # Date/time from created_at
                record_date, created_time = parse_datetime_field(row.get('created_at'))
                if record_date is None:
                    raise ValueError(
                        f"Could not parse date from created_at='{row.get('created_at')}'"
                    )
                if created_time is None:
                    from datetime import time as dt_time
                    created_time = dt_time(0, 0)

                # Duplicate detection (same key as DB UniqueConstraint)
                key = (record_date, farm.pk if farm else None, ai_disease_id)
                if key in existing_keys or ai_disease_id in existing_ids:
                    reporter.tick('skipped')
                    continue

                obj = AIDisease(
                    ai_disease_id=ai_disease_id,
                    user_id=user_id,
                    lat=lat,
                    lng=lng,
                    farm=farm,
                    crop_name=crop_name,
                    created_at=created_time,
                    language=get_str(row, 'language'),
                    original_disease=get_str(row, 'original_disease'),
                    changed_disease=get_str(row, 'changed_disease'),
                    other_diseases=get_str(row, 'other_diseases'),
                    country_code=get_str(row, 'country_code'),
                    county=get_str(row, 'county'),
                    state=get_str(row, 'state'),
                    region=get_str(row, 'region'),
                    location_name=get_str(row, 'location_name'),
                    record_date=record_date,
                    created_date=timezone.now().date(),
                )

                if not dry_run:
                    buffer.append(obj)
                    if len(buffer) >= batch_size:
                        flush_buffer()

                # Track for future duplicate detection within this same file
                existing_keys.add(key)
                existing_ids.add(ai_disease_id)
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