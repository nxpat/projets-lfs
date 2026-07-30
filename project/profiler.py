import time

from flask import g, request
from sqlalchemy import event
from sqlalchemy.engine import Engine


def setup_query_profiler(app):
    """Hooks into SQLAlchemy engine execution to audit request latency."""

    @app.before_request
    def start_timer():
        g.start_time = time.time()
        g.query_count = 0
        g.query_durations = []

    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info["query_start_time"] = time.time()

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "query_start_time" in conn.info:
            duration = time.time() - conn.info["query_start_time"]
            if hasattr(g, "query_count"):
                g.query_count += 1
                g.query_durations.append((statement[:120], duration))

    @app.after_request
    def log_request(response):
        if request.path.startswith("/static/") or request.path.endswith(
            (".css", ".js", ".png", ".jpg", ".ico", ".woff2")
        ):
            return response

        if hasattr(g, "start_time"):
            total_duration = time.time() - g.start_time
            db_duration = (
                sum(dur for _, dur in g.query_durations) if hasattr(g, "query_durations") else 0
            )

            # Print directly to WSGI stream so it shows up cleanly in the server/WSGI logs
            print("\n" + "=" * 80, flush=True)
            print(f"[PROFILER] Route: {request.method} {request.path}", flush=True)
            print(f"[PROFILER] Total Request Time: {total_duration:.4f}s", flush=True)
            print(f"[PROFILER] Total SQL Queries: {g.query_count}", flush=True)
            print(f"[PROFILER] Time Spent in DB Network: {db_duration:.4f}s", flush=True)
            print(
                f"[PROFILER] Time Spent in Python/HTML: {total_duration - db_duration:.4f}s",
                flush=True,
            )

            n = 15
            if hasattr(g, "query_durations") and g.query_durations:
                print(f"[PROFILER] Top {n} Slowest Queries:", flush=True)
                sorted_queries = sorted(g.query_durations, key=lambda x: x[1], reverse=True)[:n]
                for stmt, dur in sorted_queries:
                    print(f"    - {dur:.4f}s | {stmt}...", flush=True)
            print("=" * 80 + "\n", flush=True)
        return response
