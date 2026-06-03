"""
Web Scraper — извлечение данных с веб-страниц.
Usage: python scraper.py <url> [options]
"""
import argparse, json, os, sys
from pathlib import Path

def scrape_url(url, args):
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("Install: pip install requests beautifulsoup4")
        sys.exit(1)

    headers = {'User-Agent': 'Mozilla/5.0 (compatible; OWLBot/2.0)'}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        sys.exit(1)

    soup = BeautifulSoup(resp.text, 'html.parser')

    if args.links:
        for a in soup.find_all('a', href=True):
            print(a['href'])
    elif args.images:
        for img in soup.find_all('img', src=True):
            print(img['src'])
    elif args.css:
        for el in soup.select(args.css):
            if args.attr:
                print(el.get(args.attr, ''))
            else:
                print(el.get_text(strip=True))
    elif args.json:
        data = {
            'url': url,
            'title': soup.title.string if soup.title else '',
            'text': soup.get_text(separator='\n', strip=True)[:5000],
            'links': [a['href'] for a in soup.find_all('a', href=True)][:50],
        }
        result = json.dumps(data, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(result, encoding='utf-8')
            print(f"Saved: {args.output}")
        else:
            print(result)
    else:
        # Default: extract text
        text = soup.get_text(separator='\n', strip=True)
        if args.output:
            Path(args.output).write_text(text, encoding='utf-8')
            print(f"Saved: {args.output}")
        else:
            print(text[:int(args.max_chars)])

def main():
    parser = argparse.ArgumentParser(description='Web Scraper')
    parser.add_argument('url')
    parser.add_argument('--output', '-o')
    parser.add_argument('--links', action='store_true', help='Extract links')
    parser.add_argument('--images', action='store_true', help='Extract images')
    parser.add_argument('--css', help='CSS selector')
    parser.add_argument('--attr', help='Extract attribute instead of text')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--max-chars', default='5000')
    args = parser.parse_args()
    scrape_url(args.url, args)

if __name__ == '__main__':
    main()
