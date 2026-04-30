#!/usr/bin/env python3
"""
Compress worship sheet images from Dropbox to WebP for CDN delivery.

Downloads images from the Dropbox worship folder, resizes to 1200px wide
WebP at quality 82, and saves under public/sheets/{week_folder}/.

A manifest.json tracks file revisions so unchanged files are skipped.

GitHub Secrets required:
  DROPBOX_APP_KEY
  DROPBOX_REFRESH_TOKEN
  DROPBOX_TEAM_ROOT_ID
"""
import json
import os
import re
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WORSHIP_PATH = '/06-办公室电脑惠普HP/敬拜团歌谱'
TARGET_WIDTH  = 1200
WEBP_QUALITY  = 82
OUTPUT_DIR    = Path('public/sheets')
MANIFEST_FILE = OUTPUT_DIR / 'manifest.json'
FORCE_ALL     = os.environ.get('FORCE_ALL', 'false').lower() == 'true'

APP_KEY      = os.environ['DROPBOX_APP_KEY']
REFRESH_TOKEN= os.environ['DROPBOX_REFRESH_TOKEN']
TEAM_ROOT_ID = os.environ['DROPBOX_TEAM_ROOT_ID']

IMAGE_RE = re.compile(r'\.(jpg|jpeg|png|gif|webp)$', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Dropbox auth
# ---------------------------------------------------------------------------
def get_access_token() -> str:
    r = requests.post(
        'https://api.dropboxapi.com/oauth2/token',
        data={'grant_type': 'refresh_token',
              'refresh_token': REFRESH_TOKEN,
              'client_id': APP_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()['access_token']


def _path_root_header() -> str:
    return json.dumps({'.tag': 'root', 'root': TEAM_ROOT_ID}, ensure_ascii=True)


def dbx_api(token: str, endpoint: str, body: dict) -> dict:
    r = requests.post(
        f'https://api.dropboxapi.com{endpoint}',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Dropbox-API-Path-Root': _path_root_header(),
        },
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def dbx_download(token: str, path: str) -> bytes:
    r = requests.post(
        'https://content.dropboxapi.com/2/files/download',
        headers={
            'Authorization': f'Bearer {token}',
            'Dropbox-API-Path-Root': _path_root_header(),
            'Dropbox-API-Arg': json.dumps({'path': path}, ensure_ascii=True),
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_name(name: str) -> str:
    """Sanitize folder/file name for filesystem and URLs."""
    return re.sub(r'[^\w\-.]', '_', name)


def is_week_folder(name: str) -> bool:
    return bool(re.match(r'^\d{8}_', name))


def compress_image(raw: bytes) -> bytes:
    """Resize to TARGET_WIDTH and encode as WebP."""
    im = Image.open(BytesIO(raw))
    if im.mode in ('RGBA', 'P', 'LA'):
        im = im.convert('RGB')
    w, h = im.size
    if w > TARGET_WIDTH:
        new_h = round(h * TARGET_WIDTH / w)
        im = im.resize((TARGET_WIDTH, new_h), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, 'WEBP', quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f'Connecting to Dropbox (FORCE_ALL={FORCE_ALL})...')
    token = get_access_token()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load revision manifest (tracks which Dropbox revs are already compressed)
    manifest: dict = {}
    if MANIFEST_FILE.exists() and not FORCE_ALL:
        manifest = json.loads(MANIFEST_FILE.read_text('utf-8'))

    # List week folders
    data = dbx_api(token, '/2/files/list_folder',
                   {'path': WORSHIP_PATH, 'recursive': False, 'limit': 200})
    week_folders = [e for e in data['entries']
                    if e['.tag'] == 'folder' and is_week_folder(e['name'])]
    print(f'Found {len(week_folders)} week folders')

    total_compressed = 0
    total_skipped = 0
    total_errors = 0

    for folder in week_folders:
        fname = folder['name']
        safe_folder = safe_name(fname)
        out_dir = OUTPUT_DIR / safe_folder
        out_dir.mkdir(exist_ok=True)

        # List images inside the week folder
        try:
            fdata = dbx_api(token, '/2/files/list_folder',
                            {'path': folder['path_lower'], 'recursive': False, 'limit': 200})
        except Exception as exc:
            print(f'  [SKIP] {fname}: cannot list folder — {exc}')
            continue

        images = [e for e in fdata['entries']
                  if e['.tag'] == 'file' and IMAGE_RE.search(e['name'])]
        images.sort(key=lambda e: e['name'])

        folder_manifest = manifest.get(fname, {})
        new_folder_manifest = {}

        for img in images:
            orig_name = img['name']
            rev       = img['rev']
            webp_name = re.sub(r'\.[^.]+$', '', orig_name) + '.webp'
            out_path  = out_dir / safe_name(webp_name)

            # Skip if revision matches and output exists
            if not FORCE_ALL and folder_manifest.get(orig_name) == rev and out_path.exists():
                new_folder_manifest[orig_name] = rev
                total_skipped += 1
                continue

            print(f'  Compressing  {fname}/{orig_name} ...', end=' ', flush=True)
            try:
                raw        = dbx_download(token, img['path_lower'])
                webp_bytes = compress_image(raw)
                out_path.write_bytes(webp_bytes)
                new_folder_manifest[orig_name] = rev
                kb_orig = len(raw) // 1024
                kb_new  = len(webp_bytes) // 1024
                pct     = round((1 - kb_new / kb_orig) * 100) if kb_orig else 0
                print(f'{kb_orig}KB -> {kb_new}KB (-{pct}%)')
                total_compressed += 1
            except Exception as exc:
                print(f'ERROR: {exc}')
                total_errors += 1

        manifest[fname] = new_folder_manifest

    # Save manifest
    MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), 'utf-8')

    print(f'\nDone: {total_compressed} compressed, '
          f'{total_skipped} skipped, {total_errors} errors')

    if total_errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
