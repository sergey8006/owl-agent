# AI Image Gen

Генерация изображений: графики, QR-коды, плейсхолдеры, шаблоны для соцсетей.

## Использование

```bash
# Графики
python image_gen_tool.py chart "10,20,30,25,40" chart.png --type line --title "Sales"
python image_gen_tool.py chart "5,10,3,8" bar.png --type bar --labels "A,B,C,D"
python image_gen_tool.py chart "30,20,50" pie.png --type pie --labels "X,Y,Z"

# QR-код
python image_gen_tool.py qr "https://example.com" qr.png

# Плейсхолдер
python image_gen_tool.py placeholder ph.png --size 800,600 --color "#2d2d2d" --text "Coming Soon"

# Шаблон для соцсетей
python image_gen_tool.py social post.png --platform twitter --text "Hello World" --font-size 64
```

## Зависимости
- matplotlib, Pillow (pip install matplotlib pillow)
- qrcode (опционально: pip install qrcode)
