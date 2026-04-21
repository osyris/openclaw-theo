#!/usr/bin/env python3
import argparse
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path('/data/workspace')
INDEX = ROOT / 'pages' / 'screenshots' / 'index.json'
SHOT_ROOT = ROOT / 'pages' / 'screenshots'

VALID_CATEGORIES = {
    'books','hair','cosmetics-skincare','cosmetics-decorative','perfume','coaching','blog','fashion','home',
    'travel-ideas','food','games','health','finds','places-selfcare','leisure'
}


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9а-яё\s\-]", "", text)
    text = text.replace('ё', 'e')
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip('-')
    return text or 'item'


def main():
    p = argparse.ArgumentParser(description='Add screenshot item into pages/screenshots/index.json')
    p.add_argument('--input', required=True, help='Path to source image')
    p.add_argument('--category', required=True, choices=sorted(VALID_CATEGORIES))
    p.add_argument('--title', required=True)
    p.add_argument('--description', default='')
    p.add_argument('--source', default='')
    p.add_argument('--tags', default='', help='Comma-separated tags')
    p.add_argument('--catalog', default=None, help='Optional catalog key (e.g. skincare/hair/books/decorative/perfume)')
    p.add_argument('--filename', default=None, help='Optional destination filename (without folder)')
    args = p.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f'Input not found: {src}')

    with INDEX.open('r', encoding='utf-8') as f:
        data = json.load(f)

    max_id = max((item.get('id', 0) for item in data), default=0)
    item_id = max_id + 1

    ext = src.suffix.lower() or '.jpg'
    if args.filename:
        fname = args.filename
    else:
        fname = f"{slugify(args.title)}{ext}"

    dest_rel = Path(args.category) / fname
    dest_abs = SHOT_ROOT / dest_rel
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    if dest_abs.exists():
        base = dest_abs.stem
        i = 2
        while dest_abs.exists():
            dest_abs = dest_abs.with_name(f"{base}-{i}{ext}")
            i += 1
        dest_rel = dest_abs.relative_to(SHOT_ROOT)

    shutil.copy2(src, dest_abs)

    tags = [t.strip() for t in args.tags.split(',') if t.strip()]

    entry = {
        'id': item_id,
        'file': str(dest_rel).replace('\\', '/'),
        'category': args.category,
        'title': args.title,
        'description': args.description,
        'source': args.source if args.source else None,
        'tags': tags,
        'added': str(date.today()),
        'catalog': args.catalog
    }

    data.append(entry)

    with INDEX.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(json.dumps(entry, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
