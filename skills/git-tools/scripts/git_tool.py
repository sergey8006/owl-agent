"""
Git Tools — работа с git-репозиториями.
Usage: python git_tool.py <command> [options]

Commands:
  status     — статус репозитория
  log        — история коммитов
  diff       — изменения
  commit     — создать коммит
  branch     — управление ветками
  init       — инициализация репозитория
  analyze    — анализ репозитория
  ignore     — генерация .gitignore
"""
import argparse, os, subprocess, sys
from pathlib import Path

def run_git(args, cmd):
    result = subprocess.run(['git'] + cmd, capture_output=True, text=True, cwd=args.repo)
    if result.returncode != 0 and result.stderr:
        print(f"Error: {result.stderr.strip()}", file=sys.stderr)
    if result.stdout:
        print(result.stdout.strip())
    return result.returncode

def cmd_status(args):
    run_git(args, ['status', '-s', '-b'])

def cmd_log(args):
    cmd = ['log', f'--max-count={args.count}', '--oneline']
    if args.author:
        cmd.extend(['--author', args.author])
    run_git(args, cmd)

def cmd_diff(args):
    cmd = ['diff']
    if args.staged:
        cmd.append('--staged')
    run_git(args, cmd)

def cmd_commit(args):
    run_git(args, ['add', '-A'])
    run_git(args, ['commit', '-m', args.message])

def cmd_branch(args):
    if args.create:
        run_git(args, ['checkout', '-b', args.create])
    elif args.delete:
        run_git(args, ['branch', '-d', args.delete])
    else:
        run_git(args, ['branch', '-a'])

def cmd_init(args):
    run_git(args, ['init'])
    if args.readme:
        readme = Path(args.repo) / 'README.md'
        readme.write_text(f"# {Path(args.repo).name}\n")
        run_git(args, ['add', 'README.md'])
        run_git(args, ['commit', '-m', 'Initial commit'])
    print(f"Initialized: {args.repo}")

def cmd_analyze(args):
    # Top committers
    result = subprocess.run(['git', 'shortlog', '-sn', '--all'], capture_output=True, text=True, cwd=args.repo)
    print("Top committers:")
    for line in result.stdout.strip().split('\n')[:10]:
        print(f"  {line}")
    # File count
    result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, cwd=args.repo)
    files = result.stdout.strip().split('\n')
    print(f"\nFiles: {len(files)}")
    # Repo size
    result = subprocess.run(['git', 'count-objects', '-v'], capture_output=True, text=True, cwd=args.repo)
    for line in result.stdout.strip().split('\n'):
        if 'size' in line:
            print(f"  {line}")

def cmd_ignore(args):
    templates = {
        'python': ['__pycache__/', '*.pyc', '*.pyo', '.env', 'venv/', '*.egg-info/', 'dist/', 'build/'],
        'node': ['node_modules/', 'dist/', 'build/', '.env', '*.log'],
        'java': ['*.class', '*.jar', 'target/', '.gradle/', 'build/'],
        'go': ['*.exe', '*.test', 'vendor/', 'go.sum'],
        'rust': ['target/', 'Cargo.lock', '*.rlib'],
        'general': ['.DS_Store', 'Thumbs.db', '*.swp', '*.swo', '.idea/', '.vscode/'],
    }
    lang = args.lang or 'general'
    lines = templates.get(lang, templates['general'])
    content = '\n'.join(lines) + '\n'
    ignore_path = Path(args.repo) / '.gitignore'
    ignore_path.write_text(content)
    print(f".gitignore created ({lang}): {ignore_path}")

def main():
    parser = argparse.ArgumentParser(description='Git Tools')
    sub = parser.add_subparsers(dest='command')
    for p in sub.choices.values() if hasattr(sub, 'choices') else []:
        pass

    p = sub.add_parser('status'); p.add_argument('--repo', default='.')
    p = sub.add_parser('log'); p.add_argument('--repo', default='.'); p.add_argument('--count', type=int, default=20); p.add_argument('--author')
    p = sub.add_parser('diff'); p.add_argument('--repo', default='.'); p.add_argument('--staged', action='store_true')
    p = sub.add_parser('commit'); p.add_argument('--repo', default='.'); p.add_argument('--message', '-m', required=True)
    p = sub.add_parser('branch'); p.add_argument('--repo', default='.'); p.add_argument('--create'); p.add_argument('--delete')
    p = sub.add_parser('init'); p.add_argument('--repo', default='.'); p.add_argument('--readme', action='store_true')
    p = sub.add_parser('analyze'); p.add_argument('--repo', default='.')
    p = sub.add_parser('ignore'); p.add_argument('--repo', default='.'); p.add_argument('--lang', choices=['python','node','java','go','rust','general'])

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
