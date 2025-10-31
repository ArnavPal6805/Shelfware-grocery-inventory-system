import sqlite3
import os

here = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(here, 'employees.db')

con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute("SELECT COUNT(*) FROM inventory WHERE expiry_date IS NULL")
nulls = cur.fetchone()[0]
print('NULL expiry remaining:', nulls)

cur.execute("SELECT inventory_id, arrival_date, expiry_date FROM inventory ORDER BY inventory_id LIMIT 10")
rows = cur.fetchall()
print('Sample rows:')
for r in rows:
    print(r)

con.close()
