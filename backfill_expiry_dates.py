import os
import sqlite3
import random
from datetime import datetime, timedelta
import shutil

DB_NAME = 'employees.db'
BACKUP_SUFFIX = '.bak'

# Randomization bounds (in days)
MIN_DAYS = 30
MAX_DAYS = 180


def parse_date(date_str):
    if not date_str:
        return None
    # Try common formats
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except Exception:
            pass
    return None


def gen_random_expiry(base: datetime | None) -> str:
    days = random.randint(MIN_DAYS, MAX_DAYS)
    anchor = base or datetime.utcnow()
    dt = anchor + timedelta(days=days)
    return dt.strftime('%Y-%m-%d')


def backup_db(db_path: str) -> str:
    backup_path = db_path + BACKUP_SUFFIX
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    here = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(here, DB_NAME)

    if not os.path.exists(db_path):
        raise SystemExit(f"Database not found at {db_path}")

    # Backup first
    backup_path = backup_db(db_path)
    print(f"Backup created: {backup_path}")

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Fetch inventory rows with NULL expiry_date
    cur.execute("""
        SELECT i.inventory_id, i.arrival_date
        FROM inventory i
        WHERE i.expiry_date IS NULL
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} inventory rows with NULL expiry_date")

    updated = 0
    sample = []

    for inv_id, arrival in rows:
        base = parse_date(arrival) if arrival else None
        expiry = gen_random_expiry(base)
        cur.execute("UPDATE inventory SET expiry_date = ? WHERE inventory_id = ?", (expiry, inv_id))
        updated += 1
        if len(sample) < 5:
            sample.append((inv_id, arrival, expiry))

    con.commit()
    con.close()

    print(f"Updated {updated} rows with random expiry dates (between {MIN_DAYS} and {MAX_DAYS} days)")
    if sample:
        print("Sample updates (inventory_id, arrival_date -> expiry_date):")
        for s in sample:
            print(f"  {s[0]}: {s[1]} -> {s[2]}")


if __name__ == '__main__':
    main()
