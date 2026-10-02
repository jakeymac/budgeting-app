"""Resolve the content-hashed React bundle through Vite's build manifest."""

import json
import threading
from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static

register = template.Library()

ENTRY = 'src/main.jsx'
MANIFEST_NAME = 'frontend/manifest.json'

_cache = None
_lock = threading.Lock()


def _manifest_path():
    """Prefer the collected tree (what runs in production), fall back to the source tree."""
    collected = settings.STATIC_ROOT and (settings.STATIC_ROOT / 'frontend' / 'manifest.json')
    if collected and collected.exists():
        return collected
    found = finders.find(MANIFEST_NAME)
    return Path(found) if found else None


def _load():
    path = _manifest_path()
    if path is None:
        raise ImproperlyConfigured(
            'The React bundle has not been built. Run:\n'
            '    cd frontend && npm install && npm run build'
        )
    manifest = json.loads(path.read_text(encoding='utf-8'))
    entry = manifest.get(ENTRY)
    if not entry:
        raise ImproperlyConfigured(f'{path} has no entry for {ENTRY}. Rebuild the frontend.')
    return {
        'js': static(f'frontend/{entry["file"]}'),
        'css': [static(f'frontend/{href}') for href in entry.get('css', [])],
    }


@register.simple_tag
def frontend_assets():
    """Return {'js': url, 'css': [urls]} for the built React entry point."""
    global _cache
    if settings.DEBUG:
        return _load()
    with _lock:
        if _cache is None:
            _cache = _load()
    return _cache
