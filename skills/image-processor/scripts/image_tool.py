"""
Image Processor — работа с изображениями через Pillow.
Usage: python image_tool.py <command> [options]

Commands:
  convert    — конвертация между форматами
  resize     — изменение размера
  crop       — обрезка
  rotate     — поворот
  text       — наложение текста
  exif       — извлечение EXIF-данных
  collage    — создание коллажа
  ascii      — ASCII-art из изображения
"""
import argparse, os, sys
from PIL import Image, ImageDraw, ImageFont, ExifTags

def cmd_convert(args):
    img = Image.open(args.input)
    if args.output.lower().endswith('.jpg') or args.output.lower().endswith('.jpeg'):
        img = img.convert('RGB')
    img.save(args.output)
    print(f"Saved: {args.output}")

def cmd_resize(args):
    img = Image.open(args.input)
    if args.percent:
        w = int(img.width * args.percent / 100)
        h = int(img.height * args.percent / 100)
    else:
        w, h = args.width, args.height
    img = img.resize((w, h), Image.LANCZOS)
    img.save(args.output)
    print(f"Resized: {img.width}x{img.height} → {w}x{h}")

def cmd_crop(args):
    img = Image.open(args.input)
    img = img.crop((args.left, args.top, args.right, args.bottom))
    img.save(args.output)
    print(f"Cropped: {img.width}x{img.height}")

def cmd_rotate(args):
    img = Image.open(args.input)
    img = img.rotate(args.angle, expand=True)
    img.save(args.output)
    print(f"Rotated: {args.angle}°")

def cmd_text(args):
    img = Image.open(args.input)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(args.font, args.size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    pos = tuple(map(int, args.position.split(',')))
    draw.text(pos, args.text, fill=args.color, font=font)
    img.save(args.output)
    print(f"Text added at {pos}")

def cmd_exif(args):
    img = Image.open(args.input)
    exif = img.getexif()
    if not exif:
        print("No EXIF data")
        return
    for tag_id, value in exif.items():
        tag = ExifTags.TAGS.get(tag_id, tag_id)
        print(f"  {tag}: {value}")

def cmd_collage(args):
    images = []
    size = tuple(map(int, args.cell_size.split(',')))
    for f in args.files:
        img = Image.open(f)
        img = img.resize(size, Image.LANCZOS)
        images.append(img)
    cols = args.cols
    rows = (len(images) + cols - 1) // cols
    canvas = Image.new('RGB', (cols * size[0], rows * size[1]), 'white')
    for i, img in enumerate(images):
        x = (i % cols) * size[0]
        y = (i // cols) * size[1]
        canvas.paste(img, (x, y))
    canvas.save(args.output)
    print(f"Collage: {len(images)} images, {cols}x{rows}")

def cmd_ascii(args):
    img = Image.open(args.input)
    chars = args.chars
    w = args.width
    h = int(w * img.height / img.width * 0.5)
    img = img.resize((w, h)).convert('L')
    pixels = list(img.getdata())
    result = []
    for i in range(0, len(pixels), w):
        row = pixels[i:i+w]
        result.append(''.join(chars[min(p * (len(chars)-1) // 255, len(chars)-1)] for p in row))
    ascii_art = '\n'.join(result)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(ascii_art)
        print(f"ASCII art saved: {args.output}")
    else:
        print(ascii_art)

def main():
    parser = argparse.ArgumentParser(description='Image Processor')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('convert')
    p.add_argument('input'); p.add_argument('output')

    p = sub.add_parser('resize')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--width', type=int); p.add_argument('--height', type=int)
    p.add_argument('--percent', type=float)

    p = sub.add_parser('crop')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--left', type=int); p.add_argument('--top', type=int)
    p.add_argument('--right', type=int); p.add_argument('--bottom', type=int)

    p = sub.add_parser('rotate')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--angle', type=float, default=90)

    p = sub.add_parser('text')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--text', required=True); p.add_argument('--position', default='10,10')
    p.add_argument('--size', type=int, default=24); p.add_argument('--color', default='white')
    p.add_argument('--font', default='')

    p = sub.add_parser('exif')
    p.add_argument('input')

    p = sub.add_parser('collage')
    p.add_argument('files', nargs='+'); p.add_argument('output')
    p.add_argument('--cols', type=int, default=3); p.add_argument('--cell-size', default='200,200')

    p = sub.add_parser('ascii')
    p.add_argument('input'); p.add_argument('output', nargs='?')
    p.add_argument('--width', type=int, default=80)
    p.add_argument('--chars', default=' .:-=+*#%@')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    globals()[f'cmd_{args.command}'](args)

if __name__ == '__main__':
    main()
