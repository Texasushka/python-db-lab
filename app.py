from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import psycopg2
import time


def connect_db(connect_timeout=3):
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout = connect_timeout,
    )

def get_db_connection():
    attempts = 5

    for attempt in range(1, attempts + 1):
        print(f"Trying database connection. Attempt {attempt}/{attempts}", flush=True)

        try:
            conn = connect_db(connect_timeout=3)
            print("Database connection successful", flush=True)
            return conn

        except Exception as error:
            print(
                f"Database connection failed. Attempt {attempt}/{attempts}. "
                f"Error type: {type(error).__name__}. Error: {error}",
                flush=True
            )

            if attempt == attempts:
                raise

            time.sleep(2)

def check_db_once():
    conn = connect_db(connect_timeout =1)
    cur = conn.cursor()
    cur.execute("SELECT 1;")

    cur.close()
    conn.close()

def write_response(handler, body):
    try:
        if isinstance(body, str):
            body = body.encode()
        handler.wfile.write(body)
    except BrokenPipeError:
        print("Client disconnected before respopnse was fully sent", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            write_response(self, b"OK\n")
            return
        if self.path == "/ready":
            try:
                check_db_once()

                self.send_response(200)
                self.end_headers()
                write_response(self,b"READY\n")
                return
            except Exception as error:
                self.send_response(503)
                self.end_headers()
                write_response(self,f"NOT READY: {error}")
                return
#        if self.path ==  "/crash":
#            self.send_response(200)
#            self.end_headers()
#            self.wfile.write(b"Crashing app\n")
#            os._exit(1)
        if self.path == "/headers":
            self.send_response(200)
            self.end_headers()

            response = ""
            response += f"Host: {self.headers.get('Host')}\n"
            response += f"X-Real-IP: {self.headers.get('X-Real-IP')}\n"
            response += f"X-Forwarded-For: {self.headers.get('X-Forwarded-For')}\n"
            response += f"X-Forwarded-Proto: {self.headers.get('X-Forwarded-Proto')}\n"

            write_response(self,response.encode())
            return
        if self.path == "/stats":
            try:
                conn = get_db_connection()
                cur = conn.cursor()

                cur.execute("SELECT COUNT(*) FROM requests;")
                total_requests = cur.fetchone()[0]

                cur.execute("""
                    SELECT app_hostname, COUNT(*)
                    FROM requests
                    GROUP BY app_hostname
                    ORDER BY app_hostname;
                     """)
                rows = cur.fetchall()
                cur.close()

                self.send_response(200)
                self.end_headers()

                response=""
                response += f"\nTotal requests: {total_requests}\n\n"
                response += "Requests by container:\n"

                for app_hostname, count in rows:
                    response += f"{app_hostname} : {count}\n"
                
                write_response(self,response)
                return
            
            except Exception as error:
                self.send_response(503)
                self.end_headers()
                write_response(self,"Database unavailable: {error}")
                return
        try:
            conn = get_db_connection()
        except Exception as error:
            self.send_response(503)
            self.end_headers()
            write_response(self,f"Database unavailable: {error}")
            return

        hostname = os.environ.get("HOSTNAME", "unknown")

        cur = conn.cursor()
        cur.execute("INSERT INTO requests (app_hostname) VALUES (%s) RETURNING id, requested_at;",
                    (hostname,))
        request_id, request_at = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        self.send_response(200)
        self.end_headers()

        response = ""
        response += f"\nRequest ID:{request_id}\n"
        response += f"Container: {hostname}\n"
        response += f"Database time: {request_at}\n"

        write_response(self,response)

server = HTTPServer(("0.0.0.0", 8000), Handler)
server.serve_forever()
