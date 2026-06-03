"""
Data Tools — конвертация, валидация, анализ данных.
Usage: python data_tool.py <command> [options]

Commands:
  convert    — конвертация между JSON/CSV/YAML/TOML
  validate   — валидация JSON/YAML
  stats      — статистика CSV
  merge      — слияние JSON-файлов
  diff       — сравнение двух JSON
  generate   — генерация тестовых данных
  chart      — создание графика из CSV
"""
import argparse, csv, json, os, sys
from pathlib import Path

def load_file(path):
    ext = path.suffix.lower()
    with open(path, 'r', encoding='utf-8') as f:
        if ext == '.json':
            return json.load(f)
        elif ext in ('.yaml', '.yml'):
            import yaml
            return yaml.safe_load(f)
        elif ext == '.toml':
            import toml
            return toml.load(f)
        elif ext == '.csv':
            return list(csv.DictReader(f))
        else:
            return f.read()

def save_file(path, data):
    ext = path.suffix.lower()
    with open(path, 'w', encoding='utf-8') as f:
        if ext == '.json':
            json.dump(data, f, ensure_ascii=False, indent=2)
        elif ext in ('.yaml', '.yml'):
            import yaml
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        elif ext == '.toml':
            import toml
            toml.dump(data, f)
        elif ext == '.csv':
            if isinstance(data, list) and data:
                w = csv.DictWriter(f, fieldnames=data[0].keys())
                w.writeheader()
                w.writerows(data)
        else:
            f.write(str(data))
    print(f"Saved: {args.output}")

def cmd_convert(args):
    data = load_file(Path(args.input))
    save_file(Path(args.output), data)

def cmd_validate(args):
    try:
        load_file(Path(args.input))
        print(f"Valid: {args.input}")
    except Exception as e:
        print(f"Invalid: {e}")
        sys.exit(1)

def cmd_stats(args):
    data = load_file(Path(args.input))
    if not isinstance(data, list):
        print("Not tabular data")
        return
    print(f"Rows: {len(data)}")
    if data:
        print(f"Columns: {', '.join(data[0].keys())}")
        if args.column and args.column in data[0]:
            vals = [float(r[args.column]) for r in data if r.get(args.column, '').strip()]
            if vals:
                print(f"\nStats for '{args.column}':")
                print(f"  Count: {len(vals)}")
                print(f"  Min: {min(vals)}")
                print(f"  Max: {max(vals)}")
                print(f"  Avg: {sum(vals)/len(vals):.2f}")

def cmd_merge(args):
    result = {}
    for f in args.files:
        data = load_file(Path(f))
        if isinstance(data, dict):
            result.update(data)
        elif isinstance(data, list):
            result[Path(f).stem] = data
    save_file(Path(args.output), result)

def cmd_diff(args):
    a = load_file(Path(args.file1))
    b = load_file(Path(args.file2))
    if a == b:
        print("Files are identical")
        return
    if isinstance(a, dict) and isinstance(b, dict):
        all_keys = set(a) | set(b)
        for k in sorted(all_keys):
            if k not in a:
                print(f"  + {k}: {b[k]}")
            elif k not in b:
                print(f"  - {k}: {a[k]}")
            elif a[k] != b[k]:
                print(f"  ~ {k}: {a[k]} → {b[k]}")

def cmd_generate(args):
    import random, string
    rows = []
    for i in range(args.count):
        row = {}
        for col in args.columns.split(','):
            col = col.strip()
            if col.endswith(':int'):
                name = col[:-4]
                row[name] = random.randint(0, 1000)
            elif col.endswith(':float'):
                name = col[:-6]
                row[name] = round(random.uniform(0, 100), 2)
            elif col.endswith(':str'):
                name = col[:-4]
                row[name] = ''.join(random.choices(string.ascii_lowercase, k=8))
            elif col.endswith(':name'):
                name = col[:-5]
                first = ['Иван', 'Петр', 'Сергей', 'Анна', 'Мария', 'Ольга', 'Дмитрий', 'Алексей']
                last = ['Иванов', 'Петров', 'Сидоров', 'Козлов', 'Новиков', 'Морозов', 'Волков', 'Соколов']
                row[name] = f"{random.choice(first)} {random.choice(last)}"
            elif col.endswith(':date'):
                name = col[:-5]
                from datetime import datetime, timedelta
                d = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 2000))
                row[name] = d.strftime('%Y-%m-%d')
            else:
                row[col] = f"value_{i}"
        rows.append(row)
    save_file(Path(args.output), rows)
    print(f"Generated {args.count} rows")

def cmd_chart(args):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")
        return
    data = load_file(Path(args.input))
    if not isinstance(data, list) or not data:
        print("Need tabular data (CSV/JSON)")
        return
    col = args.column
    if col not in data[0]:
        print(f"Column '{col}' not found. Available: {', '.join(data[0].keys())}")
        return
    vals = []
    for r in data:
        try:
            vals.append(float(r[col]))
        except (ValueError, TypeError):
            pass
    if not vals:
        print("No numeric data in column")
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    if args.type == 'bar':
        ax.bar(range(len(vals)), vals)
    elif args.type == 'hist':
        ax.hist(vals, bins=args.bins)
    else:
        ax.plot(vals)
    ax.set_title(args.title or f"{col} ({args.type})")
    ax.set_xlabel(col)
    plt.tight_layout()
    plt.savefig(args.output, dpi=150)
    print(f"Chart saved: {args.output}")

def main():
    parser = argparse.ArgumentParser(description='Data Tools')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('convert')
    p.add_argument('input'); p.add_argument('output')

    p = sub.add_parser('validate')
    p.add_argument('input')

    p = sub.add_parser('stats')
    p.add_argument('input'); p.add_argument('--column', '-c')

    p = sub.add_parser('merge')
    p.add_argument('files', nargs='+'); p.add_argument('output')

    p = sub.add_parser('diff')
    p.add_argument('file1'); p.add_argument('file2')

    p = sub.add_parser('generate')
    p.add_argument('output'); p.add_argument('--count', type=int, default=10)
    p.add_argument('--columns', default='id:int,name,email:str')

    p = sub.add_parser('chart')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--column', required=True)
    p.add_argument('--type', choices=['line','bar','hist'], default='line')
    p.add_argument('--title'); p.add_argument('--bins', type=int, default=20)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
