#!/usr/bin/env python3
"""Esegue SQL sul DB Postgres/Supabase del progetto spese-ms.

Usa le credenziali DATASOURCE_* dal .env (le stesse di config.py).
Pensato per essere invocato dalla skill `db-change`.

Uso:
    python run_sql.py --file migrations/add_x.sql        # esegue un file .sql (in transazione)
    python run_sql.py --sql "SELECT 1"                   # esegue uno statement inline
    python run_sql.py --file ... --query                 # stampa le righe risultanti (SELECT)
    python run_sql.py --check-table spese.expenses       # mostra le colonne di una tabella
    python run_sql.py --list-tables                      # elenca le tabelle dello schema 'spese'

Tutto in UNA transazione: se un qualsiasi statement fallisce, rollback completo.
Eseguire da: C:\\projects\\spese-ms (root del progetto).
"""
import argparse
import os
import sys

# Carica il .env dalla root del progetto, a prescindere da dove viene lanciato
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    sys.exit("psycopg2 non installato. Attiva il venv: .venv\\Scripts\\activate")


def _conn():
    host = os.environ.get("DATASOURCE_URL")
    port = os.environ.get("DATASOURCE_PORT")
    dbname = os.environ.get("DATASOURCE_DB_NAME")
    user = os.environ.get("DATASOURCE_USERNAME")
    password = os.environ.get("DATASOURCE_PASSWORD")
    missing = [k for k, v in {
        "DATASOURCE_URL": host, "DATASOURCE_PORT": port,
        "DATASOURCE_DB_NAME": dbname, "DATASOURCE_USERNAME": user,
        "DATASOURCE_PASSWORD": password,
    }.items() if not v]
    if missing:
        sys.exit(f"Credenziali mancanti nel .env: {', '.join(missing)}")
    return psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password,
        connect_timeout=15,
    )


def _print_rows(cur):
    rows = cur.fetchall()
    if not rows:
        print("(0 righe)")
        return
    cols = list(rows[0].keys())
    print(" | ".join(cols))
    print("-" * 60)
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    print(f"\n({len(rows)} righe)")


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="percorso a un file .sql da eseguire")
    g.add_argument("--sql", help="statement SQL inline")
    g.add_argument("--check-table", metavar="SCHEMA.TABLE", help="mostra colonne di una tabella")
    g.add_argument("--list-tables", action="store_true", help="elenca tabelle schema 'spese'")
    p.add_argument("--query", action="store_true", help="stampa le righe (per SELECT)")
    args = p.parse_args()

    if args.list_tables:
        sql = ("SELECT table_name FROM information_schema.tables "
               "WHERE table_schema = 'spese' ORDER BY table_name")
        query = True
    elif args.check_table:
        schema, _, table = args.check_table.partition(".")
        if not table:
            schema, table = "spese", schema
        sql = ("SELECT column_name, data_type, is_nullable, column_default "
               "FROM information_schema.columns "
               f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
               "ORDER BY ordinal_position")
        query = True
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            sql = fh.read()
        query = args.query
    else:
        sql = args.sql
        query = args.query

    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor if query else None)
        cur.execute(sql)
        if query:
            _print_rows(cur)
        else:
            print(f"OK. Righe interessate: {cur.rowcount if cur.rowcount != -1 else 'n/a'}")
        conn.commit()
        print("Commit eseguito.")
    except Exception as e:
        conn.rollback()
        print(f"ERRORE (rollback eseguito): {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
