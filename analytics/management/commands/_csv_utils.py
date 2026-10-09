# analytics/management/commands/_csv_utils.py
"""
Shared CSV parsing utilities for management commands.
"""
import csv
import io
import json
import re
from datetime import datetime, time, timedelta
from django.utils import timezone


FULL_DATETIME_FORMATS = [
   
    '%Y-%m-%d %H:%M:%S.%f',      
  
    '%Y-%m-%d %H:%M:%S',        
    '%Y-%m-%d %H:%M',           
    '%Y-%m-%dT%H:%M:%S.%f',   
    '%Y-%m-%dT%H:%M:%S',      
    '%Y-%m-%dT%H:%M',           
    '%m/%d/%Y %I:%M:%S %p',     
    '%m/%d/%Y %H:%M:%S',      
    '%m/%d/%Y %I:%M %p',    
    '%m/%d/%Y %H:%M',          
    '%m/%d/%y %I:%M:%S %p',     
    '%m/%d/%Y, %I:%M:%S %p',    
    # European formats
    '%d/%m/%Y %H:%M:%S',       
    '%d/%m/%Y %I:%M:%S %p',   
    '%d-%m-%Y %H:%M:%S',        
    # Date-only (will get midnight time)
    '%Y-%m-%d',             
    '%m/%d/%Y',                 
    '%d/%m/%Y',             
]

TIME_ONLY_FORMATS = [
    '%H:%M:%S.%f',  
    '%H:%M:%S',     
    '%H:%M',        
    '%I:%M:%S %p',  
    '%I:%M %p',     
    '%M:%S.%f',     
    '%M:%S',       
]


def is_blank(value):
    """Check if a value is blank/null/nan."""
    if value is None:
        return True
    s = str(value).strip()
    return s == '' or s.lower() in ('null', 'none', 'nan', 'nat')


def parse_datetime_field(value):
    """
    Parse a datetime field that might contain date, time, or both.
    Returns (date, time) tuple. Either can be None.
    """
    if is_blank(value):
        return None, None

    raw_val = str(value).strip()

    # Try full datetime formats first (gives us both date and time)
    for fmt in FULL_DATETIME_FORMATS:
        try:
            dt = datetime.strptime(raw_val, fmt)
            return dt.date(), dt.time()
        except ValueError:
            continue

    # Try Excel serial number
    if re.match(r'^\d+(\.\d+)?$', raw_val):
        try:
            excel_serial = float(raw_val)
            # Excel's epoch quirk (1900 leap year bug)
            if excel_serial > 60:
                excel_serial -= 1
            excel_epoch = datetime(1899, 12, 31)
            dt = excel_epoch + timedelta(days=excel_serial)
            return dt.date(), dt.time()
        except (ValueError, OverflowError):
            pass

    # Try time-only formats
    for fmt in TIME_ONLY_FORMATS:
        try:
            time_obj = datetime.strptime(raw_val, fmt).time()
            return None, time_obj
        except ValueError:
            continue

    return None, None


def parse_time_only(value):
    """Parse only the time portion of a field, returning a time or None."""
    if is_blank(value):
        return None
    _, t = parse_datetime_field(value)
    return t

# CSV READING


def read_csv_rows(file_path):
    """
    Read a CSV file and return (headers, rows_as_dicts).
    Handles UTF-8 and ISO-8859-1 fallback, and sniffs dialect.
    """
    with open(file_path, 'rb') as f:
        raw = f.read()

    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('ISO-8859-1')

    # Sniff dialect (delimiter, quoting)
    try:
        dialect = csv.Sniffer().sniff(text[:4096])
    except csv.Error:
        dialect = 'excel'

    io_string = io.StringIO(text)
    reader = csv.DictReader(io_string, dialect=dialect)

    # Normalize headers to lowercase/stripped for robust matching
    fieldnames = reader.fieldnames or []
    normalized_map = {name: name.strip().lower() for name in fieldnames}

    rows = []
    for raw_row in reader:
        normalized = {}
        for orig_key, val in raw_row.items():
            if orig_key is None:
                continue
            normalized[normalized_map.get(orig_key, orig_key.strip().lower())] = val
        rows.append(normalized)

    return [h.strip().lower() for h in fieldnames], rows


def get_str(row, key, default=None):
    """Get a stripped string value from a row dict."""
    val = row.get(key)
    if is_blank(val):
        return default
    return str(val).strip()


def get_int(row, key, required=True):
    """Get an int, or return None for empty optional values."""

    raw = get_str(row, key)

    if raw is None:
        if required:
            raise ValueError(f"'{key}' is required")
        return None

    try:
        return int(float(raw))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {key} '{raw}' - must be a number")


def get_float(row, key, required=False):
    """Get a float or None."""
    raw = get_str(row, key)
    if raw is None:
        if required:
            raise ValueError(f"'{key}' is required")
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"Invalid {key} '{raw}' - must be a number")


def parse_threats(value):
    """Parse a JSON-ish threats list from CSV."""
    if is_blank(value):
        return None
    raw = str(value).strip()
    if raw in ('[]', '[ ]'):
        return []
    try:
        return json.loads(raw.replace("'", '"'))
    except json.JSONDecodeError:
        # Fall back to comma splitting
        stripped = raw.strip('[]')
        if not stripped:
            return []
        return [t.strip().strip("'\"") for t in stripped.split(',') if t.strip()]


# PROGRESS REPORTER

class ProgressReporter:
    """Simple stderr progress reporter."""

    def __init__(self, total=None, prefix='', every=500):
        self.total = total
        self.prefix = prefix
        self.every = every
        self.count = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0

    def tick(self, status='processed'):
        self.count += 1
        if status == 'created':
            self.created += 1
        elif status == 'updated':
            self.updated += 1
        elif status == 'skipped':
            self.skipped += 1
        elif status == 'error':
            self.errors += 1

        if self.count % self.every == 0:
            self.print_status()

    def print_status(self):
        if self.total:
            pct = (self.count / self.total) * 100
            line = (
                f"{self.prefix} {self.count}/{self.total} ({pct:.1f}%) "
                f"| created={self.created} updated={self.updated} "
                f"skipped={self.skipped} errors={self.errors}"
            )
        else:
            line = (
                f"{self.prefix} processed={self.count} "
                f"| created={self.created} updated={self.updated} "
                f"skipped={self.skipped} errors={self.errors}"
            )
        print(line)