import os
import csv
import json
import uuid
from decimal import Decimal
from datetime import datetime, date, time

from django.apps import apps
from django.db import transaction
from django.db.models import (
    ForeignKey,
    UUIDField,
    DateField,
    DateTimeField,
    TimeField,
    DecimalField,
    IntegerField,
    FloatField,
    BooleanField,
    JSONField,
)
 
BASE_DIR = os.getcwd()
CSV_DIRECTORY = os.path.join(BASE_DIR, "imported")     # folder containing your csv files



def parse_value(field, value):
    if value in ("", None):
        return None

    if isinstance(field, UUIDField):
        return uuid.UUID(value)

    if isinstance(field, IntegerField):
        return int(value)

    if isinstance(field, FloatField):
        return float(value)

    if isinstance(field, DecimalField):
        return Decimal(value)

    if isinstance(field, BooleanField):
        return value.lower() in ("1", "true", "yes")

    import ast
    if isinstance(field, JSONField):

        value = value.strip()

        try:
            return json.loads(value)

        except Exception:
            return ast.literal_eval(value)

    if isinstance(field, DateTimeField):
        return datetime.fromisoformat(value)

    if isinstance(field, DateField):

        value = value.strip()

        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass

        raise ValueError(f"Invalid date format: {value}")

    if isinstance(field, TimeField):

        value = value.strip()

        try:
            return time.fromisoformat(value)

        except ValueError:

            # Handle MM:SS or MM:SS.s
            if "." in value:
                mins_secs, frac = value.split(".")
            else:
                mins_secs = value
                frac = "0"

            mins, secs = mins_secs.split(":")

            return time(
                hour=0,
                minute=int(mins),
                second=int(secs),
                microsecond=int(float("0." + frac) * 1_000_000),
            )

    return value


def model_depth(model):
    """
    Parents first.
    """
    depth = 0

    for field in model._meta.fields:
        if isinstance(field, ForeignKey):
            depth += 1

    return depth


models = sorted(
    apps.get_models(),
    key=model_depth
)

for model in models:

    table = model._meta.db_table
    csv_file = os.path.join(CSV_DIRECTORY, f"{table}.csv")

    if not os.path.exists(csv_file):
        print(f"Skipping {table} (CSV not found)")
        continue

    print(f"\nImporting {table}")

    imported = 0
    failed = 0

    with open(csv_file, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        with transaction.atomic():

            for row in reader:

                try:

                    obj = {}

                    for field in model._meta.fields:

                        name = field.name

                        if isinstance(field, ForeignKey):

                            raw = row.get(name)

                            if raw in ("", None):
                                obj[name] = None
                                continue

                            target = field.remote_field.model

                            obj[name] = target.objects.get(
                                **{field.target_field.name: parse_value(field.target_field, raw)}
                            )

                        else:

                            obj[name] = parse_value(
                                field,
                                row.get(name)
                            )

                    model.objects.create(**obj)

                    imported += 1

                except Exception as e:

                    failed += 1

                    print(f"Failed row in {table}")
                    print(e)

    print(f"Imported : {imported}")
    print(f"Failed   : {failed}")

print("\nDONE.")