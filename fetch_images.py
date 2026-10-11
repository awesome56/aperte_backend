"""Fetch actual images from source listings for properties lacking a real image.

Designed to run inside the app context (uses the same storage module + DB models).
Usage: python fetch_images.py [--only=<id>] [--dry-run]
"""
import os, re, io, sys, json
from pathlib import Path
import requests
from werkzeug.datastructures import FileStorage

# ---- load .env ----
env_file = Path('/home/lenovo/aperte_backend/.env')
for line in env_file.read_text().splitlines():
    line = line.strip()
    if line and '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k, v.strip().strip("'\""))

from src import create_app
from src.database import db, Property, PropertyImage

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# Generic/site-chrome image names to exclude.
BAD = re.compile(r'logo|favicon|icon|behance|facebook\.jpg|twitter\.jpg|whatsapp|navbar|app-image|room-sample|img-og|google-play|app-store|\.svg|hotelsng/', re.I)

def domain(url):
    return re.sub(r'^https?://', '', url).split('/')[0]

def extract_images(source, html):
    """Return candidate real listing image URLs, host-aware, excluding site chrome."""
    imgs = set()
    dm = domain(source)
    # hotels.ng: real hotel gallery photos (hotel-specific, not generic fallbacks)
    for m in re.findall(r'https://images\.hotels\.ng/hotels/\d+/[a-zA-Z0-9]+_900x550\.jpg', html):
        imgs.add(m)
    # hotels.ng real images via timbu CDN
    for m in re.findall(r'https://images\.timbu\.com/hotels-ng/hotel_[^"\'\\ ]+\.(?:jpg|jpeg|png)', html):
        imgs.add(m)
    # propertypro real images
    for m in re.findall(r'https://images\.propertypro\.ng/(?:large|medium)/[^"\'\\ ]+\.(?:jpg|jpeg|png|webp)', html):
        imgs.add(m)
    # finelib: listing-specific image (company_logo / tn images hosted on finelib)
    for m in re.findall(r'https?://[^"\'\\ ]*finelib\.com/images/listings/[^"\'\\ ]+\.(?:JPG|jpg|jpeg|png|webp)', html):
        imgs.add(m)
    # generic og:image, but only on a trusted host and not site chrome
    og = re.search(r'og:image" content="([^"]+)"', html)
    if og:
        u = og.group(1)
        if not BAD.search(u):
            imgs.add(u)
    # Deduplicate and drop any URL whose host is malformed (e.g. hotels.nghotels-ng)
    cleaned = []
    for u in sorted(imgs):
        host = re.sub(r'^https?://', '', u).split('/')[0]
        if not host or host.count('.') < 2 or 'nghotels' in host:
            continue
        cleaned.append(u)
    return cleaned

def upload_bytes(data, filename, prefix):
    fs = FileStorage(stream=io.BytesIO(data), filename=filename)
    from src.constants.storage import upload_file
    return upload_file(fs, prefix)

def main():
    args = sys.argv[1:]
    only = None
    dry = '--dry-run' in args
    for a in args:
        if a.startswith('--only='):
            only = int(a.split('=', 1)[1])

    app = create_app()
    with app.app_context():
        # Target properties lacking a real image
        props = (Property.query
                 .outerjoin(PropertyImage, db.and_(PropertyImage.property_id == Property.id, PropertyImage.dp == 1))
                 .filter((PropertyImage.id.is_(None)) |
                         (PropertyImage.image_url.like('%app-image.png')) |
                         (PropertyImage.image_url.like('%room-sample%')))
                 .order_by(Property.id).all())

        if only:
            props = [p for p in props if p.id == only]
            if not props:
                # allow fetching even if currently counts as real (fallback)
                props = [Property.query.get(only)] if Property.query.get(only) else []

        results = []
        for p in props:
            if not p.source:
                results.append((p.id, 'skipped', 'no source'))
                continue
            try:
                r = requests.get(p.source, headers=HEADERS, timeout=30, allow_redirects=True)
                if r.status_code != 200:
                    results.append((p.id, 'error', 'http {}'.format(r.status_code)))
                    continue
                imgs = extract_images(p.source, r.text)
            except Exception as e:
                results.append((p.id, 'error', str(e)))
                continue

            if not imgs:
                results.append((p.id, 'no-image', 'source has no extractable real image'))
                continue

            # Try each candidate until one downloads successfully.
            chosen_url = None
            chosen = None
            for url in imgs:
                try:
                    ir = requests.get(url, headers=HEADERS, timeout=30)
                    if ir.status_code == 200 and len(ir.content) > 500:
                        chosen_url = url
                        chosen = ir
                        break
                except Exception:
                    continue
            if chosen is None:
                results.append((p.id, 'no-image', 'could not download any candidate image from source'))
                continue

            filename = chosen_url.rsplit('/', 1)[-1]
            prefix = 'properties/{}/images'.format(p.user_id)
            if dry:
                results.append((p.id, 'dry', '{} -> {} ({} bytes)'.format(p.source, chosen_url, len(chosen.content))))
                continue

            try:
                new_url = upload_bytes(chosen.content, filename, prefix)
            except Exception as e:
                results.append((p.id, 'error', 'upload: {}'.format(e)))
                continue

            # Clear existing dp, then add new image as dp (if property had none, dp=1;
            # if it had placeholder images, still promote real image to dp).
            existing_real = PropertyImage.query.filter_by(property_id=p.id).count()
            was_placeholder = existing_real > 0
            # Promote new image to dp; demote any other dp rows.
            PropertyImage.query.filter_by(property_id=p.id, dp=1).update({'dp': 0})
            pi = PropertyImage(property_id=p.id, image_url=new_url, dp=1,
                               created_at=p.created_at, updated_at=p.updated_at)
            db.session.add(pi)
            if was_placeholder:
                # remove the placeholder/generic images so they don't clutter the gallery
                PropertyImage.query.filter_by(property_id=p.id).filter(
                    (PropertyImage.image_url.like('%app-image.png')) |
                    (PropertyImage.image_url.like('%room-sample%')) |
                    (PropertyImage.image_url.like('%google-play%')) |
                    (PropertyImage.image_url.like('%app-store%'))
                ).delete(synchronize_session=False)
            db.session.commit()
            results.append((p.id, 'ok', 'added {} (dp, {} bytes)'.format(new_url, len(chosen.content))))

        for rid, status, detail in results:
            print("{:>5}  {:<10}  {}".format(rid, status, detail))
        print("\nProcessed {} properties".format(len(results)))

if __name__ == '__main__':
    main()
