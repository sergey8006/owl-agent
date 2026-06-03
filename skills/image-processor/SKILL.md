# Image Processor

Обработка изображений: конвертация, ресайз, обрезка, поворот, текст, EXIF, коллажи, ASCII-art.

## Использование

```bash
# Конвертация форматов
python image_tool.py convert input.png output.jpg

# Изменение размера
python image_tool.py resize input.jpg output.jpg --width 800 --height 600
python image_tool.py resize input.jpg output.jpg --percent 50

# Обрезка
python image_tool.py crop input.jpg output.jpg --left 100 --top 100 --right 500 --bottom 400

# Поворот
python image_tool.py rotate input.jpg output.jpg --angle 90

# Наложение текста
python image_tool.py text input.jpg output.jpg --text "Hello" --position 50,50 --size 32 --color white

# EXIF-данные
python image_tool.py exif photo.jpg

# Коллаж
python image_tool.py collage img1.jpg img2.jpg img3.jpg output.jpg --cols 2 --cell-size 300,300

# ASCII-art
python image_tool.py ascii input.jpg --width 100
python image_tool.py ascii input.jpg output.txt --width 120 --chars " .:-=+*#%@"
```

## Зависимости
- Pillow (pip install pillow)
