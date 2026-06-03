"""
Archive Tools — работа с архивами.
Usage: python archive_tool.py <command> [options]

Commands:
  create     — создать архив
  extract    — распаковать архив
  list       — список содержимого
  compare    — сравнить два архива
"""
import argparse, filecmp, os, sys, tarfile, zipfile
from pathlib import Path

def cmd_create(args):
    fmt = args.format or Path(args.output).suffix.lstrip('.')
    if fmt in ('zip',):
        import zipfile
        with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in args.files:
                p = Path(f)
                if p.is_dir():
                    for fp in p.rglob('*'):
                        if fp.is_file():
                            zf.write(fp, fp.relative_to(p.parent))
                elif p.is_file():
                    zf.write(p, p.name)
        print(f"Created: {args.output}")
    elif fmt in ('tar', 'gz', 'tgz', 'bz2', 'xz'):
        mode = 'w'
        if fmt in ('gz', 'tgz'):
            mode = 'w:gz'
        elif fmt == 'bz2':
            mode = 'w:bz2'
        elif fmt == 'xz':
            mode = 'w:xz'
        with tarfile.open(args.output, mode) as tf:
            for f in args.files:
                tf.add(f, arcname=Path(f).name)
        print(f"Created: {args.output}")
    else:
        print(f"Unsupported format: {fmt}")
        sys.exit(1)

def cmd_extract(args):
    p = Path(args.input)
    if p.suffix == '.zip':
        with zipfile.ZipFile(args.input, 'r') as zf:
            if args.list_only:
                for name in zf.namelist():
                    info = zf.getinfo(name)
                    print(f"  {info.file_size:>10} {name}")
            else:
                zf.extractall(args.output or '.')
                print(f"Extracted to: {args.output or '.'}")
    elif p.suffix in ('.tar', '.gz', '.tgz', '.bz2', '.xz') or '.tar.' in p.name:
        with tarfile.open(args.input, 'r:*') as tf:
            if args.list_only:
                for m in tf.getmembers():
                    print(f"  {m.size:>10} {m.name}")
            else:
                tf.extractall(args.output or '.')
                print(f"Extracted to: {args.output or '.'}")
    else:
        print(f"Unknown format: {p.suffix}")
        sys.exit(1)

def cmd_list(args):
    p = Path(args.input)
    if p.suffix == '.zip':
        with zipfile.ZipFile(args.input, 'r') as zf:
            for info in zf.infolist():
                print(f"  {info.file_size:>10} {info.filename}")
    elif '.tar' in p.name or p.suffix in ('.gz', '.bz2', '.xz', '.tgz'):
        with tarfile.open(args.input, 'r:*') as tf:
            for m in tf.getmembers():
                print(f"  {m.size:>10} {m.name}")

def cmd_compare(args):
    def get_names(path):
        p = Path(path)
        if p.suffix == '.zip':
            with zipfile.ZipFile(path, 'r') as zf:
                return set(zf.namelist())
        elif '.tar' in p.name or p.suffix in ('.gz', '.bz2', '.xz', '.tgz'):
            with tarfile.open(path, 'r:*') as tf:
                return set(m.name for m in tf.getmembers() if m.isfile())
        return set()
    a = get_names(args.archive1)
    b = get_names(args.archive2)
    only_a = a - b
    only_b = b - a
    common = a & b
    if only_a:
        print(f"Only in {args.archive1}:")
        for f in sorted(only_a):
            print(f"  - {f}")
    if only_b:
        print(f"Only in {args.archive2}:")
        for f in sorted(only_b):
            print(f"  + {f}")
    print(f"Common: {len(common)} files")
    if only_a or only_b:
        print(f"Different: {len(only_a) + len(only_b)} files")
    else:
        print("Archives have the same file list")

def main():
    parser = argparse.ArgumentParser(description='Archive Tools')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('create')
    p.add_argument('files', nargs='+'); p.add_argument('output')
    p.add_argument('--format', '-f')

    p = sub.add_parser('extract')
    p.add_argument('input'); p.add_argument('--output', '-o')
    p.add_argument('--list-only', action='store_true')

    p = sub.add_parser('list')
    p.add_argument('input')

    p = sub.add_parser('compare')
    p.add_argument('archive1'); p.add_argument('archive2')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
