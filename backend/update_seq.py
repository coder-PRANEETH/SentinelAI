import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to {db_url}")
conn = psycopg2.connect(db_url)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT setval('dispatch_id_seq', 100);")
    cur.execute("SELECT setval('incident_id_seq', 100);")
print("Sequences updated successfully!")
