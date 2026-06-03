"""
System Monitor — мониторинг системы.
Usage: python system_tool.py <command> [options]

Commands:
  info       — общая информация о системе
  cpu        — информация о CPU
  memory     — информация о памяти
  disk       — информация о дисках
  network    — информация о сети
  processes  — список процессов
  ports      — открытые порты
  packages   — установленные пакеты
"""
import argparse, os, platform, socket, subprocess, sys
from pathlib import Path

def cmd_info(args):
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Node: {platform.node()}")
    print(f"Arch: {platform.machine()}")
    print(f"Python: {platform.python_version()}")
    print(f"Hostname: {socket.gethostname()}")
    try:
        with open('/proc/uptime') as f:
            up = float(f.read().split()[0])
        h, m = divmod(int(up) // 60, 60)
        d, h = divmod(h, 24)
        print(f"Uptime: {d}d {h}h {m}m")
    except:
        pass

def cmd_cpu(args):
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if 'model name' in line:
                    print(f"CPU: {line.split(':')[1].strip()}")
                    break
        with open('/proc/cpuinfo') as f:
            cores = sum(1 for l in f if l.startswith('processor'))
        print(f"Cores: {cores}")
        with open('/proc/loadavg') as f:
            load = f.read().split()[:3]
        print(f"Load: {' '.join(load)}")
    except FileNotFoundError:
        print("CPU info not available")

def cmd_memory(args):
    try:
        with open('/proc/meminfo') as f:
            mem = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(':')] = int(parts[1])
        total = mem.get('MemTotal', 0) // 1024
        free = mem.get('MemFree', 0) // 1024
        avail = mem.get('MemAvailable', 0) // 1024
        used = total - avail
        print(f"Total: {total} MB")
        print(f"Used: {used} MB ({used*100//total if total else 0}%)")
        print(f"Free: {free} MB")
        print(f"Available: {avail} MB")
        swap_total = mem.get('SwapTotal', 0) // 1024
        swap_free = mem.get('SwapFree', 0) // 1024
        if swap_total:
            print(f"Swap: {swap_total} MB (used: {swap_total - swap_free} MB)")
    except FileNotFoundError:
        print("Memory info not available")

def cmd_disk(args):
    try:
        result = subprocess.run(['df', '-h'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if args.path:
            for line in lines:
                if args.path in line:
                    print(line)
        else:
            for line in lines[:20]:
                print(line)
    except FileNotFoundError:
        print("df not available")

def cmd_network(args):
    try:
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
        current_iface = None
        for line in result.stdout.split('\n'):
            if line and not line.startswith(' '):
                current_iface = line.split(':')[1].strip() if ':' in line else None
            if 'inet ' in line and current_iface:
                ip = line.strip().split()[1]
                print(f"{current_iface}: {ip}")
    except FileNotFoundError:
        try:
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            print(result.stdout[:1000])
        except:
            print("Network info not available")
    print(f"\nHostname: {socket.gethostname()}")
    try:
        print(f"FQDN: {socket.getfqdn()}")
    except:
        pass

def cmd_processes(args):
    try:
        result = subprocess.run(['ps', 'aux', '--sort=-%mem'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        print(lines[0])
        for line in lines[1:args.limit+1]:
            if args.search and args.search.lower() not in line.lower():
                continue
            print(line)
    except FileNotFoundError:
        print("ps not available")

def cmd_ports(args):
    try:
        result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'LISTEN' in line:
                print(line)
    except FileNotFoundError:
        try:
            result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
            print(result.stdout[:2000])
        except:
            print("Port info not available")

def cmd_packages(args):
    try:
        result = subprocess.run(['pip3', 'list'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if args.search:
            lines = [l for l in lines if args.search.lower() in l.lower()]
        for line in lines[:args.limit]:
            print(line)
        print(f"\nTotal shown: {min(len(lines)-2, args.limit)}")
    except FileNotFoundError:
        print("pip not available")

def main():
    parser = argparse.ArgumentParser(description='System Monitor')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('info')
    sub.add_parser('cpu')
    sub.add_parser('memory')
    p = sub.add_parser('disk'); p.add_argument('--path')
    sub.add_parser('network')
    p = sub.add_parser('processes')
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--search', '-s')
    sub.add_parser('ports')
    p = sub.add_parser('packages')
    p.add_argument('--search', '-s')
    p.add_argument('--limit', type=int, default=50)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
