"""
Database Tools — работа с SQLite.
Usage: python db_tool.py <command> [options]

Commands:
  query      — выполнить SQL-запрос
  tables     — список таблиц
  schema     — схема таблицы
  export     — экспорт таблицы в CSV/JSON
  import     — импорт из CSV в таблицу
  backup     — бэкап базы
  optimize   — VACUUM + ANALYZE
  stats      — статистика БД
"""
import argparse, csv, json, os, sqlite3, shutil, sys
from pathlib import Path

def get_db(path):
    return sqlite3.connect(path)

def cmd_query(args):
    conn = get_db(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(args.sql)
    if args.sql.strip().upper().startswith('SELECT'):
        rows = cur.fetchall()
        if rows:
            cols = rows[0].keys()
            print('\t'.join(cols))
            for r in rows[:args.limit]:
                print('\t'.join(str(r[c]) for c in cols))
            if len(rows) > args.limit:
                print(f"... ({len(rows)} total, showing {args.limit})")
        else:
            print("No results")
    else:
        conn.commit()
        print(f"Affected: {cur.rowcount} rows")
    conn.close()

def cmd_tables(args):
    conn = get_db(args.db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cur.fetchone()[0]
        print(f"  {t} ({count} rows)")
    print(f"\nTotal: {len(tables)} tables")
    conn.close()

def cmd_schema(args):
    conn = get_db(args.db)
    cur = conn.cursor()
    if args.table:
        cur.execute(f"PRAGMA table_info([{args.table}])")
        rows = cur.fetchall()
        print(f"Table: {args.table}")
        for r in rows:
            pk = " PRIMARY KEY" if r[5] else ""
            null = " NOT NULL" if r[3] else ""
            print(f"  {r[1]}: {r[2]}{null}{pk}")
        cur.execute(f"PRAGMA index_list([{args.table}])")
        indexes = cur.fetchall()
        if indexes:
            print("Indexes:")
            for idx in indexes:
                print(f"  {idx[1]} ({'unique' if idx[2] else 'non-unique'})")
    else:
        cur.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
        for r in cur.fetchall():
            print(r[0])
    conn.close()

def cmd_export(args):
    conn = get_db(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM [{args.table}]")
    rows = [dict(r) for r in cur.fetchall()]
    ext = Path(args.output).suffix.lower()
    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        if ext == '.json':
            json.dump(rows, f, ensure_ascii=False, indent=2)
        elif ext == '.csv':
            if rows:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
    print(f"Exported {len(rows)} rows → {args.output}")
    conn.close()

def cmd_import(args):
    conn = get_db(args.db)
    cur = conn.cursor()
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        print("No data in CSV")
        return
    cols = list(rows[0].keys())
    placeholders = ','.join(['?'] * len(cols))
    cur.execute(f"CREATE TABLE IF NOT EXISTS [{args.table}] ({', '.join(cols)})")
    cur.executemany(f"INSERT INTO [{args.table}] VALUES ({placeholders})", [tuple(r[c] for c in cols) for r in rows])
    conn.commit()
    print(f"Imported {len(rows)} rows → {args.table}")
    conn.close()

def cmd_backup(args):
    src = Path(args.db)
    dst = Path(args.output) if args.output else src.with_suffix('.backup.db')
    shutil.copy2(src, dst)
    print(f"Backup: {src} → {dst} ({dst.stat().st_size:,} bytes)")

def cmd_optimize(args):
    conn = get_db(args.db)
    conn.execute("VACUUM")
    conn.execute("ANALYZE")
    size = Path(args.db).stat().st_size
    print(f"Optimized. Size: {size:,} bytes")
    conn.close()

def cmd_stats(args):
    conn = get_db(args.db)
    cur = conn.cursor()
    size = Path(args.db).stat().st_size
    print(f"Database: {args.db}")
    print(f"Size: {size:,} bytes ({size//1024} KB)")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {len(tables)}")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        print(f"  {t}: {cur.fetchone()[0]} rows")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='Database Tools')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('query')
    p.add_argument('db'); p.add_argument('sql')
    p.add_argument('--limit', type=int, default=100)

    p = sub.add_parser('tables')
    p.add_argument('db')

    p = sub.add_parser('schema')
    p.add_argument('db'); p.add_argument('--table', '-t')

    p = sub.add_parser('export')
    p.add_argument('db'); p.add_argument('table'); p.add_argument('output')

    p = sub.add_parser('import')
    p.add_argument('db'); p.add_argument('table'); p.add_argument('input')

    p = sub.add_parser('backup')
    p.add_argument('db'); p.add_argument('--output')

    p = sub.add_parser('optimize')
    p.add_argument('db')

    p = sub.add_parser('stats')
    p.add_argument('db')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
