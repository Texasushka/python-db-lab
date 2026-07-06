import os
import psycopg2

conn = psycopg2.connect(
    host = os.environ["DB_HOST"],
    port = os.environ["DB_PORT"],
    database = os.environ["DB_NAME"],
    user = os.environ["DB_USER"],
    password = os.environ["DB_PASSWORD"],
)

cur = conn.cursor()

cur.execute("""
            CREATE TABLE IF NOT EXISTS requests(
            id SERIAL PRIMARY KEY,
            app_hostname TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT NOW()
            );
            """)

conn.commit()
cur.close()
conn.close()

print("Migration completed successfully")