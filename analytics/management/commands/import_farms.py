# analytics/management/commands/import_farms.py
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.models import Farm
from ._csv_utils import (
    read_csv_rows, get_str, get_int, get_float,
    parse_datetime_field, ProgressReporter,
)


class Command(BaseCommand):
    help = 'Bulk import Farm records from a CSV file (terminal-only, no HTTP timeouts)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='How often to commit a transaction (default: 500)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parse and validate but do not write to the database',
        )
        parser.add_argument(
            '--skip-errors', action='store_true',
            help='Skip rows that fail instead of aborting',
        )
        parser.add_argument(
            '--stop-after-errors', type=int, default=50,
            help='Abort after this many errors (default: 50)',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        skip_errors = options['skip_errors']
        stop_after_errors = options['stop_after_errors']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Importing Farms from {csv_path}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no writes will be made"))

        start = time.time()

        try:
            headers, rows = read_csv_rows(csv_path)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        total = len(rows)
        self.stdout.write(f"Read {total} rows. Headers: {headers}")

        reporter = ProgressReporter(total=total, prefix='[Farms]')
        errors_log = []

        for idx, row in enumerate(rows, start=2):  # row 1 is header
            try:
                farm_id = get_int(row, 'farm_id')
                farm_name = get_str(row, 'farm_name')
                if not farm_name:
                    raise ValueError("'farm_name' is required")

                lat = get_float(row, 'lat')
                lng = get_float(row, 'lng')

                created_at_d, created_at_t = parse_datetime_field(row.get('created_at'))
                updated_at_d, updated_at_t = parse_datetime_field(row.get('updated_at'))
                deleted_at_d, deleted_at_t = parse_datetime_field(row.get('deleted_at'))

                # Combine date+time back to a single DateTime for Farm (it uses DateTimeField)
                def combine(d, t):
                    if d is None and t is None:
                        return None
                    from datetime import datetime, time as dt_time
                    date_part = d or timezone.now().date()
                    time_part = t or dt_time(0, 0)
                    naive = datetime.combine(date_part, time_part)
                    return timezone.make_aware(naive, timezone.get_current_timezone())

                created_at = combine(created_at_d, created_at_t)
                updated_at = combine(updated_at_d, updated_at_t)
                deleted_at = combine(deleted_at_d, deleted_at_t)

                if dry_run:
                    reporter.tick('processed')
                    continue

                with transaction.atomic():
                    _, created = Farm.objects.update_or_create(
                        farm_id=farm_id,
                        defaults={
                            'farm_name': farm_name,
                            'lat': lat,
                            'lng': lng,
                            'created_at': created_at,
                            'updated_at': updated_at,
                            'deleted_at': deleted_at,
                            'created_date': timezone.now().date(),
                        },
                    )
                reporter.tick('created' if created else 'updated')

                if reporter.count % batch_size == 0:
                    reporter.print_status()

            except Exception as e:
                reporter.tick('error')
                msg = f"Row {idx}: {e}"
                errors_log.append(msg)
                if not skip_errors:
                    raise CommandError(
                        f"Aborting on error. {msg}\n"
                        f"Use --skip-errors to continue past failures."
                    )
                if len(errors_log) >= stop_after_errors:
                    self.stdout.write(self.style.ERROR(
                        f"Stopping after {stop_after_errors} errors."
                    ))
                    break

        elapsed = time.time() - start
        reporter.print_status()

        if errors_log:
            self.stdout.write(self.style.WARNING(
                f"\n{len(errors_log)} errors:"
            ))
            for err in errors_log[:20]:
                self.stdout.write(f"  {err}")
            if len(errors_log) > 20:
                self.stdout.write(f"  ... and {len(errors_log) - 20} more")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone in {elapsed:.1f}s. "
            f"Created={reporter.created} Updated={reporter.updated} "
            f"Errors={reporter.errors}"
        ))