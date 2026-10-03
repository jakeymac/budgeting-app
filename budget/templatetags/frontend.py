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
_cache_stamp = None
_lock = threading.Lock()


def _manifest_path():
    """Prefer the collected tree (what runs in production), fall back to the source tree."""
    collected = settings.STATIC_ROOT and (settings.STATIC_ROOT / 'frontend' / 'manifest.json')
    if collected and collected.exists():
        return collected
    found = finders.find(MANIFEST_NAME)
    return Path(found) if found else None


def _load(path=None):
    path = path or _manifest_path()
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
    """Return {'js': url, 'css': [urls]} for the built React entry point.

    Cached, but keyed on the manifest's mtime and size: a deploy that replaces
    the file is picked up without waiting for the worker to be restarted. A
    worker left holding a stale manifest would serve URLs for bundles the same
    deploy has already pruned, which is a blank page.
    """
    global _cache, _cache_stamp
    if settings.DEBUG:
        return _load()
    path = _manifest_path()
    try:
        info = path.stat()
        stamp = (info.st_mtime_ns, info.st_size)
    except (OSError, AttributeError):
        # Missing manifest: fall through so _load() raises with instructions.
        stamp = None
    with _lock:
        if _cache is None or stamp is None or stamp != _cache_stamp:
            _cache, _cache_stamp = _load(path), stamp
        return _cache
