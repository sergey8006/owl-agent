# Web Scraper

Извлечение данных с веб-страниц через requests + BeautifulSoup.

## Использование

```bash
# Извлечь текст с веб-страницы
python scraper.py https://example.com
python scraper.py https://example.com --output page.txt

# Извлечь ссылки
python scraper.py https://example.py --links

# Извлечь изображения
python scraper.py https://example.com --images

# CSS-селекторы
python scraper.py https://example.com --css "div.content > p"
python scraper.py https://example.com --css "a[href]" --attr href

# Сохранить в JSON
python scraper.py https://example.com --json output.json
```

## Зависимости
- requests, beautifulsoup4 (pip install requests beautifulsoup4)
