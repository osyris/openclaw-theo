#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

ROOT = Path('/data/workspace/pages')
PAGE_MAP = {
    'skincare': ROOT / 'skincare' / 'index.html',
    'hair': ROOT / 'hair' / 'index.html',
    'decorative': ROOT / 'decorative' / 'index.html',
    'books': ROOT / 'books' / 'index.html',
}


def build_item(page: str, args):
    if page == 'books':
        return {
            'name': args.title,
            'author': args.author or '',
            'surname': '',
            'original': '',
            'genre': args.genre.split(',') if args.genre else [],
            'desc': args.desc,
            'img': args.img,
            'source': args.source or '',
            'status': 'wishlist'
        }

    base = {
        'name': args.title,
        'desc': args.desc,
        'fullDesc': args.full_desc or args.desc,
        'img': args.img,
        'imgs': [args.img],
        'price': args.price or '',
        'source': args.source or ''
    }
    return base


def append_item_to_html(html_text: str, item_obj: dict) -> str:
    # Find `const items = [ ... ];`
    m = re.search(r"const\s+items\s*=\s*\[(.*?)\]\s*;", html_text, flags=re.S)
    if not m:
        raise ValueError('Could not find `const items = [...]` block')

    inner = m.group(1).rstrip()
    item_json = json.dumps(item_obj, ensure_ascii=False, indent=2)
    item_json = '\n'.join('  ' + line for line in item_json.splitlines())

    if inner.strip():
        new_inner = inner + ',\n' + item_json + '\n'
    else:
        new_inner = '\n' + item_json + '\n'

    new_block = f"const items = [{new_inner}];"
    start, end = m.span()
    return html_text[:start] + new_block + html_text[end:]


def main():
    p = argparse.ArgumentParser(description='Append an item to static page catalog (const items array)')
    p.add_argument('--page', required=True, choices=sorted(PAGE_MAP.keys()))
    p.add_argument('--title', required=True)
    p.add_argument('--desc', required=True)
    p.add_argument('--img', required=True, help='Path relative to page folder, e.g. img/file.jpg')
    p.add_argument('--source', default='')
    p.add_argument('--price', default='')
    p.add_argument('--full-desc', default='')
    p.add_argument('--author', default='')
    p.add_argument('--genre', default='', help='Comma separated (books only)')
    args = p.parse_args()

    path = PAGE_MAP[args.page]
    if not path.exists():
        raise SystemExit(f'Page file not found: {path}')

    item = build_item(args.page, args)

    html = path.read_text(encoding='utf-8')
    updated = append_item_to_html(html, item)
    path.write_text(updated, encoding='utf-8')

    print(json.dumps({'ok': True, 'page': args.page, 'file': str(path), 'item': item}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
