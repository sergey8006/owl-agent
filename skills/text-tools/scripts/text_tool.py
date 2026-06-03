"""
Text Tools — обработка текста, поиск, конвертация.
Usage: python text_tool.py <command> [options]

Commands:
  grep       — поиск по файлам (regex)
  replace    — поиск и замена в файлах
  diff       — сравнение двух файлов
  stats      — статистика текста
  encoding   — конвертация кодировки
  base64     — кодирование/декодирование base64
  hex        — hex encode/decode
  report     — генерация markdown-отчёта
"""
import argparse, codecs, difflib, glob, os, re, sys
from collections import Counter

def cmd_grep(args):
    pattern = re.compile(args.pattern, re.IGNORECASE if args.ignore_case else 0)
    files = []
    if os.path.isfile(args.path):
        files = [args.path]
    else:
        for root, _, fnames in os.walk(args.path):
            for f in fnames:
                files.append(os.path.join(root, f))
    found = 0
    for filepath in files[:500]:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        print(f"{filepath}:{i}: {line.rstrip()}")
                        found += 1
                        if found >= args.max:
                            print(f"(stopped at {args.max} matches)")
                            return
        except (PermissionError, OSError):
            pass
    print(f"\nTotal: {found} matches in {len(files)} files")

def cmd_replace(args):
    pattern = re.compile(args.pattern)
    files = glob.glob(args.files, recursive=True)
    total = 0
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            new_content, n = pattern.subn(args.replacement, content)
            if n > 0:
                if not args.dry_run:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"  {filepath}: {n} replacements")
                else:
                    print(f"  {filepath}: {n} replacements (dry run)")
                total += n
        except (PermissionError, OSError) as e:
            print(f"  {filepath}: ERROR {e}")
    print(f"\nTotal: {total} replacements in {len(files)} files")

def cmd_diff(args):
    def read_lines(path):
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.readlines()
    a = read_lines(args.file1)
    b = read_lines(args.file2)
    diff = list(difflib.unified_diff(a, b, fromfile=args.file1, tofile=args.file2))
    if not diff:
        print("Files are identical")
    else:
        print(''.join(diff))

def cmd_stats(args):
    with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    lines = text.split('\n')
    words = re.findall(r'\b\w+\b', text.lower())
    chars = len(text)
    print(f"File: {args.input}")
    print(f"  Characters: {chars:,}")
    print(f"  Words: {len(words):,}")
    print(f"  Lines: {len(lines):,}")
    print(f"  Unique words: {len(set(words)):,}")
    if args.top:
        print(f"\nTop {args.top} words:")
        for word, count in Counter(words).most_common(args.top):
            print(f"  {word}: {count}")

def cmd_encoding(args):
    with open(args.input, 'rb') as f:
        raw = f.read()
    # Try to decode from source encoding
    try:
        text = raw.decode(args.from_enc)
    except (UnicodeDecodeError, LookupError):
        text = raw.decode('utf-8', errors='replace')
        print(f"Warning: could not decode as {args.from_enc}, used utf-8 fallback")
    if args.output:
        with open(args.output, 'w', encoding=args.to_enc) as f:
            f.write(text)
        print(f"Converted: {args.from_enc} → {args.to_enc}")
        if args.output != args.input:
            print(f"Saved: {args.output}")
    else:
        sys.stdout.buffer.write(text.encode(args.to_enc))

def cmd_base64(args):
    import base64
    with open(args.input, 'rb') as f:
        data = f.read()
    if args.decode:
        decoded = base64.b64decode(data)
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(decoded)
            print(f"Decoded: {len(decoded)} bytes")
        else:
            print(decoded.decode('utf-8', errors='replace'))
    else:
        encoded = base64.b64encode(data).decode()
        if args.output:
            with open(args.output, 'w') as f:
                f.write(encoded)
        print(encoded)

def cmd_hex(args):
    with open(args.input, 'rb') as f:
        data = f.read()
    if args.decode:
        decoded = bytes.fromhex(data.decode().strip())
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(decoded)
            print(f"Decoded: {len(decoded)} bytes")
        else:
            print(decoded.decode('utf-8', errors='replace'))
    else:
        print(data.hex())

def cmd_report(args):
    title = args.title or "Report"
    now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f"# {title}", f"", f"Generated: {now}", f""]
    if args.input and os.path.isfile(args.input):
        with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
        lines.append("## Source")
        lines.append(f"```")
        lines.append(source[:5000])
        lines.append(f"```")
    if args.data and os.path.isfile(args.data):
        import json
        with open(args.data, 'r') as f:
            data = json.load(f)
        lines.append("## Data")
        lines.append(f"```json")
        lines.append(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        lines.append(f"```")
    report = '\n'.join(lines)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
    print(f"Report generated: {len(report)} chars")

def main():
    parser = argparse.ArgumentParser(description='Text Tools')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('grep')
    p.add_argument('pattern'); p.add_argument('path')
    p.add_argument('-i', '--ignore-case', action='store_true')
    p.add_argument('--max', type=int, default=100)

    p = sub.add_parser('replace')
    p.add_argument('pattern'); p.add_argument('replacement')
    p.add_argument('files', help='glob pattern')
    p.add_argument('--dry-run', action='store_true')

    p = sub.add_parser('diff')
    p.add_argument('file1'); p.add_argument('file2')

    p = sub.add_parser('stats')
    p.add_argument('input'); p.add_argument('--top', type=int, default=10)

    p = sub.add_parser('encoding')
    p.add_argument('input'); p.add_argument('--from', dest='from_enc', default='utf-8')
    p.add_argument('--to', dest='to_enc', default='utf-8'); p.add_argument('--output')

    p = sub.add_parser('base64')
    p.add_argument('input'); p.add_argument('output', nargs='?')
    p.add_argument('--decode', action='store_true')

    p = sub.add_parser('hex')
    p.add_argument('input'); p.add_argument('output', nargs='?')
    p.add_argument('--decode', action='store_true')

    p = sub.add_parser('report')
    p.add_argument('--title', '-t'); p.add_argument('--input'); p.add_argument('--data'); p.add_argument('--output')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
