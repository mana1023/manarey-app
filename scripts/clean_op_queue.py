#!/usr/bin/env python3
"""Script para limpiar la tabla op_queue.
Uso:
    python scripts/clean_op_queue.py --keep-days 7  # elimina status=2 older than 7 days
    python scripts/clean_op_queue.py --all-done    # elimina todos los status=2
"""
import argparse
from datetime import datetime, timedelta

import models.db as mdb

parser = argparse.ArgumentParser()
parser.add_argument(
    "--keep-days",
    type=int,
    default=None,
    help="Eliminar items DONE (status=2) más viejos que N días",
)
parser.add_argument(
    "--all-done", action="store_true", help="Eliminar todos los items con status=2"
)
args = parser.parse_args()

conn = mdb.get_connection()
cur = conn.cursor()
if args.all_done:
    cur.execute("DELETE FROM op_queue WHERE status=2")
    deleted = cur.rowcount
    conn.commit()
    print(f"Eliminados {deleted} items con status=2")
elif args.keep_days is not None:
    cutoff = (datetime.now() - timedelta(days=args.keep_days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    cur.execute("DELETE FROM op_queue WHERE status=2 AND created_at<?", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    print(f"Eliminados {deleted} items con status=2 anteriores a {cutoff}")
else:
    cur.execute("SELECT COUNT(*) FROM op_queue WHERE status=2")
    print("Items DONE:", cur.fetchone()[0])

conn.close()
