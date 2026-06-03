"""
AI Image Gen — генерация изображений/графиков через matplotlib.
Usage: python image_gen_tool.py <command> [options]

Commands:
  chart      — создание графика (line, bar, pie, scatter, hist)
  qr         — генерация QR-кода
  placeholder — создание placeholder-изображения
  social     — шаблон для соцсетей
"""
import argparse, os, sys
from pathlib import Path

def cmd_chart(args):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not installed: pip install matplotlib")
        return

    fig, ax = plt.subplots(figsize=(args.width, args.height))
    data = [float(x) for x in args.data.split(',')]
    labels = args.labels.split(',') if args.labels else [str(i) for i in range(len(data))]

    if args.type == 'line':
        ax.plot(data, marker='o')
    elif args.type == 'bar':
        ax.bar(labels, data)
    elif args.type == 'pie':
        ax.pie(data, labels=labels, autopct='%1.1f%%')
    elif args.type == 'scatter':
        ax.scatter(range(len(data)), data)
    elif args.type == 'hist':
        ax.hist(data, bins=args.bins)

    ax.set_title(args.title or f"{args.type} chart")
    plt.tight_layout()
    plt.savefig(args.output, dpi=args.dpi)
    print(f"Chart saved: {args.output}")

def cmd_qr(args):
    try:
        import qrcode
        from PIL import Image
    except ImportError:
        print("qrcode not installed: pip install qrcode[pil]")
        return
    qr = qrcode.make(args.data)
    qr.save(args.output)
    print(f"QR code saved: {args.output}")

def cmd_placeholder(args):
    from PIL import Image, ImageDraw, ImageFont
    size = tuple(map(int, args.size.split(',')))
    img = Image.new('RGB', size, args.color)
    draw = ImageDraw.Draw(img)
    text = args.text or f"{size[0]}x{size[1]}"
    try:
        font = ImageFont.truetype('', args.font_size)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0]-tw)//2, (size[1]-th)//2), text, fill='white', font=font)
    img.save(args.output)
    print(f"Placeholder saved: {args.output}")

def cmd_social(args):
    from PIL import Image, ImageDraw, ImageFont
    platforms = {
        'instagram': (1080, 1080),
        'twitter': (1200, 675),
        'facebook': (1200, 630),
        'linkedin': (1200, 627),
        'youtube': (1280, 720),
    }
    size = platforms.get(args.platform, (1200, 630))
    img = Image.new('RGB', size, args.color or '#1a1a2e')
    draw = ImageDraw.Draw(img)
    text = args.text or args.platform.title()
    try:
        font = ImageFont.truetype('', args.font_size)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0]-tw)//2, (size[1]-th)//2), text, fill='white', font=font)
    img.save(args.output)
    print(f"Social template saved: {args.output}")

def main():
    parser = argparse.ArgumentParser(description='AI Image Gen')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('chart')
    p.add_argument('data', help='comma-separated values')
    p.add_argument('output')
    p.add_argument('--type', choices=['line','bar','pie','scatter','hist'], default='line')
    p.add_argument('--labels'); p.add_argument('--title')
    p.add_argument('--width', type=float, default=10); p.add_argument('--height', type=float, default=6)
    p.add_argument('--dpi', type=int, default=150); p.add_argument('--bins', type=int, default=10)

    p = sub.add_parser('qr')
    p.add_argument('data'); p.add_argument('output')

    p = sub.add_parser('placeholder')
    p.add_argument('output'); p.add_argument('--size', default='400,300')
    p.add_argument('--color', default='#333333'); p.add_argument('--text')
    p.add_argument('--font-size', type=int, default=24)

    p = sub.add_parser('social')
    p.add_argument('output'); p.add_argument('--platform', default='twitter')
    p.add_argument('--text'); p.add_argument('--color'); p.add_argument('--font-size', type=int, default=48)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
