#!/usr/bin/env python3
"""Push this project to a PythonAnywhere web app over the PythonAnywhere API.

The free tier gives CI no shell, so this does everything through the REST API:
upload the files, drop stale static assets, reload the web app, then ask the
running app to apply migrations via its /_deploy/finalize/ hook.

Standard library only, so it runs on a bare python:3.x CI image.

Required environment:
    PA_USERNAME        PythonAnywhere username
    PA_API_TOKEN       API token from the Account -> API token page
    PA_DOMAIN          e.g. yourname.pythonanywhere.com

Optional:
    PA_HOST            www.pythonanywhere.com (default) or eu.pythonanywhere.com
    PA_PROJECT_DIR     remote path (default /home/$PA_USERNAME/budget-app)
    APP_URL            public base URL (default https://$PA_DOMAIN)
    DEPLOY_TOKEN       shared secret for the finalize hook; skipped when unset
    DEPLOY_FORCE_STATIC=1  re-upload every static file, not just new paths
    DEPLOY_DRY_RUN=1   list the work without touching the server
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Source trees the web app needs. Anything else in the repo (frontend sources,
# CI config, docs) stays on GitHub.
SOURCE_PREFIXES = ('budget/', 'budget_app/', 'templates/')
SOURCE_FILES = ('manage.py', 'requirements.txt')
STATIC_DIR = 'staticfiles'

# Never delete these during a prune, whatever the manifest says.
PROTECTED = {'.env', 'db.sqlite3'}

UPLOAD_WORKERS = 4
MAX_ATTEMPTS = 5


class DeployError(RuntimeError):
    pass


def log(message):
    print(message, flush=True)


def require(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise DeployError(f'Missing required environment variable {name}.')
    return value


class PythonAnywhere:
    def __init__(self, username, token, host):
        self.username = username
        self.token = token
        self.base = f'https://{host}/api/v0/user/{username}/'

    def _call(self, method, path, *, body=None, headers=None, expect=(200, 201, 204)):
        url = urllib.parse.urljoin(self.base, path)
        request_headers = {'Authorization': f'Token {self.token}'}
        request_headers.update(headers or {})
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                payload = error.read().decode('utf-8', 'replace')[:400]
                # 429 is the API rate limiter; 5xx is usually transient.
                if error.code in (429, 500, 502, 503, 504) and attempt < MAX_ATTEMPTS:
                    delay = min(2 ** attempt, 30)
                    log(f'  {method} {path} -> {error.code}, retrying in {delay}s')
                    time.sleep(delay)
                    continue
                if error.code in expect:
                    return error.code, payload.encode()
                raise DeployError(f'{method} {path} failed with {error.code}: {payload}')
            except urllib.error.URLError as error:
                if attempt < MAX_ATTEMPTS:
                    delay = min(2 ** attempt, 30)
                    log(f'  {method} {path} -> {error.reason}, retrying in {delay}s')
                    time.sleep(delay)
                    continue
                raise DeployError(f'{method} {path} failed: {error.reason}')
        raise DeployError(f'{method} {path} exhausted retries.')

    def upload(self, remote_path, data, filename):
        boundary = f'----budget{secrets.token_hex(16)}'
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        body = b''.join([
            f'--{boundary}\r\n'.encode(),
            f'Content-Disposition: form-data; name="content"; filename="{filename}"\r\n'.encode(),
            f'Content-Type: {content_type}\r\n\r\n'.encode(),
            data,
            f'\r\n--{boundary}--\r\n'.encode(),
        ])
        quoted = urllib.parse.quote(remote_path)
        self._call('POST', f'files/path{quoted}', body=body,
                   headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})

    def delete(self, remote_path):
        self._call('DELETE', f'files/path{urllib.parse.quote(remote_path)}', expect=(204, 404))

    def tree(self, remote_path):
        status, payload = self._call('GET', f'files/tree/?path={urllib.parse.quote(remote_path)}',
                                     expect=(200, 400, 404))
        if status != 200:
            return None  # Directory does not exist yet, or holds too many entries to list.
        try:
            return [entry for entry in json.loads(payload) if not entry.endswith('/')]
        except (ValueError, TypeError):
            return None

    def reload(self, domain):
        self._call('POST', f'webapps/{domain}/reload/')


def tracked_sources():
    """Files Git knows about that the web app actually needs."""
    listing = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.split('\0')
    chosen = [
        name for name in listing
        if name and (name in SOURCE_FILES or name.startswith(SOURCE_PREFIXES))
        and not name.endswith(('.pyc',))
    ]
    missing = [name for name in chosen if not (ROOT / name).is_file()]
    if missing:
        raise DeployError(f'Tracked but missing on disk: {", ".join(missing)}')
    return sorted(chosen)


def collected_static():
    base = ROOT / STATIC_DIR
    if not base.is_dir():
        raise DeployError(
            f'{STATIC_DIR}/ is missing. Run `python manage.py collectstatic --noinput` '
            'after building the frontend.'
        )
    return sorted(
        str(path.relative_to(ROOT)) for path in base.rglob('*')
        if path.is_file() and '__pycache__' not in path.parts
    )


def main():
    username = require('PA_USERNAME')
    token = require('PA_API_TOKEN')
    domain = require('PA_DOMAIN')
    host = os.environ.get('PA_HOST', 'www.pythonanywhere.com').strip() or 'www.pythonanywhere.com'
    project_dir = (os.environ.get('PA_PROJECT_DIR', '').strip()
                   or f'/home/{username}/budget-app').rstrip('/')
    app_url = (os.environ.get('APP_URL', '').strip() or f'https://{domain}').rstrip('/')
    force_static = os.environ.get('DEPLOY_FORCE_STATIC', '') == '1'
    dry_run = os.environ.get('DEPLOY_DRY_RUN', '') == '1'

    api = PythonAnywhere(username, token, host)
    sources = tracked_sources()
    statics = collected_static()

    log(f'Deploying to {project_dir} on {host} ({len(sources)} source files, {len(statics)} static files)')

    # Static assets are content-hashed, so an existing remote path already holds
    # the right bytes. Skipping them keeps a deploy to a few dozen API calls.
    existing = set()
    if not force_static:
        listed = api.tree(f'{project_dir}/{STATIC_DIR}') if not dry_run else []
        if listed is None:
            log('  could not list remote static tree; uploading all static files')
        else:
            prefix = f'{project_dir}/'
            existing = {path[len(prefix):] for path in listed if path.startswith(prefix)}

    to_upload = sources + [name for name in statics if force_static or name not in existing]
    skipped = len(statics) - (len(to_upload) - len(sources))
    if skipped:
        log(f'  {skipped} static files already present, skipping')

    if dry_run:
        for name in to_upload:
            log(f'  would upload {name}')
        return 0

    failures = []

    def push(name):
        try:
            api.upload(f'{project_dir}/{name}', (ROOT / name).read_bytes(), Path(name).name)
        except DeployError as error:
            failures.append(f'{name}: {error}')

    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
        list(pool.map(push, to_upload))
    if failures:
        raise DeployError('Upload failed:\n  ' + '\n  '.join(failures))
    log(f'Uploaded {len(to_upload)} files.')

    # Drop superseded bundles. Limited to the collected static tree, which is
    # the only place stale files pile up, and never touches data or secrets.
    listed = api.tree(f'{project_dir}/{STATIC_DIR}')
    if listed is None:
        log('Skipping prune: remote static tree could not be listed.')
    else:
        prefix = f'{project_dir}/'
        wanted = set(statics)
        stale = [
            path for path in listed
            if path.startswith(prefix)
            and path[len(prefix):] not in wanted
            and Path(path).name not in PROTECTED
        ]
        for path in stale:
            api.delete(path)
        log(f'Pruned {len(stale)} stale static files.')

    api.reload(domain)
    log(f'Reloaded {domain}.')

    deploy_token = os.environ.get('DEPLOY_TOKEN', '').strip()
    if not deploy_token:
        log('DEPLOY_TOKEN not set: skipping migrations. Run them yourself in a PythonAnywhere console.')
        return 0

    finalize(app_url, deploy_token)
    return 0


def finalize(app_url, deploy_token):
    """Ask the freshly reloaded app to migrate and bootstrap its login."""
    url = f'{app_url}/_deploy/finalize/'
    request = urllib.request.Request(
        url, data=b'', method='POST',
        headers={'X-Deploy-Token': deploy_token, 'Content-Type': 'application/json'},
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read())
            log('Finalize output:')
            log('  ' + (payload.get('output') or '(no output)').strip().replace('\n', '\n  '))
            return
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', 'replace')[:600]
            if error.code == 404:
                raise DeployError(
                    'The finalize hook returned 404. Either the app has not picked up the new code '
                    'yet, or DEPLOY_TOKEN on PythonAnywhere does not match the one in CI.'
                )
            if attempt < MAX_ATTEMPTS:
                log(f'  finalize -> {error.code}, retrying ({detail[:120]})')
                time.sleep(min(2 ** attempt, 30))
                continue
            raise DeployError(f'Finalize failed with {error.code}: {detail}')
        except urllib.error.URLError as error:
            if attempt < MAX_ATTEMPTS:
                log(f'  finalize -> {error.reason}, retrying')
                time.sleep(min(2 ** attempt, 30))
                continue
            raise DeployError(f'Finalize failed: {error.reason}')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except DeployError as error:
        print(f'\nDeploy failed: {error}', file=sys.stderr)
        sys.exit(1)
