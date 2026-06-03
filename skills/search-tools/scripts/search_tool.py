"""
Search Tools — поиск по файлам.
Usage: python search_tool.py <command> [options]

Commands:
  grep       — полнотекстовый поиск
  regex      — поиск по регулярному выражению
  replace    — поиск и замена с превью
  duplicates — поиск дубликатов
  bigfiles   — поиск больших файлов
"""
import argparse, filecmp, hashlib, os, re, sys
from pathlib import Path
from collections import defaultdict

def get_files(path, recursive=True):
    p = Path(path)
    if p.is_file():
        return [p]
    pattern = '**/*' if recursive else '*'
    return [f for f in p.glob(pattern) if f.is_file()]

def cmd_grep(args):
    files = get_files(args.path, args.recursive)
    count = 0
    for f in files[:1000]:
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                for i, line in enumerate(fh, 1):
                    if args.pattern.lower() in line.lower():
                        print(f"{f}:{i}: {line.rstrip()}")
                        count += 1
                        if count >= args.max:
                            print(f"(stopped at {args.max} matches)")
                            return
        except (PermissionError, OSError):
            pass
    print(f"\nTotal: {count} matches")

def cmd_regex(args):
    pattern = re.compile(args.pattern, re.IGNORECASE if args.ignore_case else 0)
    files = get_files(args.path, args.recursive)
    count = 0
    for f in files[:1000]:
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                for i, line in enumerate(fh, 1):
                    m = pattern.search(line)
                    if m:
                        print(f"{f}:{i}: {line.rstrip()}")
                        count += 1
                        if count >= args.max:
                            return
        except (PermissionError, OSError):
            pass
    print(f"\nTotal: {count} matches")

def cmd_replace(args):
    pattern = re.compile(args.pattern)
    files = get_files(args.path, args.recursive)
    total = 0
    for f in files[:500]:
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                content = fh.read()
            new_content, n = pattern.subn(args.replacement, content)
            if n > 0:
                if args.dry_run:
                    print(f"  {f}: {n} matches (dry)")
                else:
                    with open(f, 'w', encoding='utf-8') as fh:
                        fh.write(new_content)
                    print(f"  {f}: {n} replaced")
                total += n
        except (PermissionError, OSError) as e:
            print(f"  {f}: ERROR {e}")
    print(f"Total: {total}")

def cmd_duplicates(args):
    files = get_files(args.path, args.recursive)
    hashes = defaultdict(list)
    for f in files:
        try:
            h = hashlib.md5(f.read_bytes()).hexdigest()
            hashes[h].append(str(f))
        except (PermissionError, OSError):
            pass
    dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
    if not dupes:
        print("No duplicates found")
        return
    for h, paths in dupes.items():
        print(f"\n[{h[:8]}]")
        for p in paths:
            print(f"  {p}")
    print(f"\nTotal: {len(dupes)} duplicate groups")

def cmd_bigfiles(args):
    files = get_files(args.path, args.recursive)
    sized = []
    for f in files:
        try:
            size = f.stat().st_size
            if size >= args.min_size * 1024:
                sized.append((size, str(f)))
        except (PermissionError, OSError):
            pass
    sized.sort(reverse=True)
    for size, path in sized[:args.limit]:
        if size >= 1048576:
            print(f"  {size//1048576} MB  {path}")
        else:
            print(f"  {size//1024} KB  {path}")
    print(f"\nTotal: {len(sized)} files >= {args.min_size}KB")

def main():
    parser = argparse.ArgumentParser(description='Search Tools')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('grep')
    p.add_argument('pattern'); p.add_argument('path'); p.add_argument('--max', type=int, default=100)
    p.add_argument('--no-recursive', dest='recursive', action='store_false', default=True)

    p = sub.add_parser('regex')
    p.add_argument('pattern'); p.add_argument('path'); p.add_argument('--max', type=int, default=100)
    p.add_argument('--ignore-case', '-i', action='store_true')
    p.add_argument('--no-recursive', dest='recursive', action='store_false', default=True)

    p = sub.add_parser('replace')
    p.add_argument('pattern'); p.add_argument('replacement'); p.add_argument('path')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-recursive', dest='recursive', action='store_false', default=True)

    p = sub.add_parser('duplicates')
    p.add_argument('path'); p.add_argument('--no-recursive', dest='recursive', action='store_false', default=True)

    p = sub.add_parser('bigfiles')
    p.add_argument('path'); p.add_argument('--min-size', type=int, default=1024)
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--no-recursive', dest='recursive', action='store_false', default=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
