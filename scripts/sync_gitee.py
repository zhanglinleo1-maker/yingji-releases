"""Copy public release assets; publish domestic links only after hash verification.

Only fixed repositories are supported. Tokens never appear in URLs or output.
Uploads are idempotent: existing same-name assets are verified, never overwritten.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

OWNER = 'zhanglinleo1-maker'
REPO = 'yingji-releases'
SLUG = OWNER + '/' + REPO
GH = 'https://api.github.com/repos/' + SLUG
GT = 'https://gitee.com/api/v5/repos/' + SLUG
DOMESTIC = 'https://gitee.com/' + SLUG + '/releases'
LIMIT = 100 * 1024 * 1024

class SyncError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def api(base, path, token, method='GET', body=None, multipart=None):
    headers = {'Authorization': 'Bearer ' + token, 'User-Agent': 'Yingji-Release-Sync', 'Accept': 'application/json'}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    if multipart is not None:
        boundary = 'Yingji' + uuid.uuid4().hex
        headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{multipart.name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + multipart.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=240) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Never print response bodies, headers, credentials, or request objects.
        raise SyncError(f'{urllib.parse.urlsplit(base).hostname} API HTTP {error.code}; no download links changed unless verification already passed') from None
    except Exception:
        raise SyncError(f'{urllib.parse.urlsplit(base).hostname} API connection failed; rerun after checking service availability') from None

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def download(url, path, allowed_hosts, max_bytes):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts:
        raise SyncError('Unapproved public download URL')
    try:
        # Anonymous: credentials cannot leak to redirected asset/CDN hosts.
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Yingji-Release-Verify'}), timeout=120) as response, path.open('wb') as f:
            if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                raise SyncError('Insecure asset redirect')
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise SyncError('Asset exceeds expected size')
                f.write(chunk)
    except SyncError:
        raise
    except Exception:
        raise SyncError('Anonymous asset download failed; metadata not advanced') from None

def prepare_installer(path, directory):
    if path.stat().st_size <= LIMIT:
        return path
    archive = directory / (path.stem + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if archive.stat().st_size > LIMIT:
        raise SyncError('Installer and ZIP exceed Gitee 100 MiB guard; no upload attempted. Prepare a smaller release first.')
    with zipfile.ZipFile(archive) as z:
        if z.namelist() != [path.name] or hashlib.sha256(z.read(path.name)).hexdigest() != sha(path):
            raise SyncError('Wrapped installer integrity failed')
    return archive

def select_release(release, manifest, tag):
    if release.get('draft') or release.get('tag_name') != tag:
        raise SyncError('Only an already published matching GitHub release may be copied')
    rows = [r for r in manifest.get('releases', []) if r.get('version') == tag[1:] and r.get('published') is True]
    if len(rows) != 1:
        raise SyncError('Missing or ambiguous published version metadata')
    row = rows[0]
    files = [a for a in release.get('assets', []) if a['name'] == f'Yingji-{tag[1:]}-win64-setup.exe']
    if len(files) != 1 or files[0]['size'] != row['size_bytes'] or files[0].get('digest') != 'sha256:' + row['sha256']:
        raise SyncError('GitHub installer does not match published version hash/size')
    return row, files[0]

def file_content(entry):
    if entry.get('encoding') != 'base64':
        raise SyncError('Unexpected repository file encoding')
    return base64.b64decode(entry['content'])

def put_file(base, token, name, content, expected_sha=None):
    entry = api(base, '/contents/' + name, token)
    if expected_sha is not None and entry['sha'] != expected_sha:
        raise SyncError('Repository file changed concurrently; rerun without overwriting newer metadata')
    if file_content(entry) == content:
        return
    api(base, '/contents/' + name, token, 'PUT', {'branch': 'main', 'sha': entry['sha'],
        'message': 'Update verified domestic downloads', 'content': base64.b64encode(content).decode()})

def ensure_asset(release_id, file, token, directory):
    path = f'/releases/{release_id}/attach_files'
    assets = api(GT, path, token)
    if not isinstance(assets, list):
        raise SyncError('Unexpected Gitee attachment list')
    matches = [a for a in assets if a.get('name') == file.name]
    if len(matches) > 1:
        raise SyncError('Duplicate Gitee asset names; refusing ambiguous downloads')
    item = matches[0] if matches else api(GT, path, token, 'POST', multipart=file)
    url = item.get('browser_download_url') or item.get('download_url')
    if not url:
        raise SyncError('Gitee did not return a public attachment URL')
    fetched = directory / ('verified-' + file.name)
    download(url, fetched, {'gitee.com'}, file.stat().st_size)
    if sha(fetched) != sha(file):
        raise SyncError('Existing/uploaded Gitee attachment hash mismatch; refusing overwrite or metadata change')

def main():
    gh_token, gt_token = os.environ.get('GH_TOKEN', ''), os.environ.get('GITEE_TOKEN', '')
    if not gh_token or not gt_token:
        raise SyncError('First-time setup required: add repository Actions secret GITEE_TOKEN; never put it in source or chat')
    tag = os.environ.get('RELEASE_TAG', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-beta\d+)?', tag):
        raise SyncError('Invalid release tag')
    release = api(GH, '/releases/tags/' + tag, gh_token)
    for attempt in range(13):
        manifest = json.loads(file_content(api(GH, '/contents/version.json', gh_token)))
        if any(r.get('version') == tag[1:] for r in manifest.get('releases', [])):
            break
        if attempt == 12:
            raise SyncError('Published version metadata is not ready; rerun after release metadata is committed')
        time.sleep(10)
    row, installer = select_release(release, manifest, tag)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        original = directory / installer['name']
        download(installer['browser_download_url'], original, {'github.com'}, row['size_bytes'])
        if sha(original) != row['sha256']:
            raise SyncError('Downloaded GitHub installer failed hash verification')
        package = prepare_installer(original, directory)
        checksums = directory / 'SHA256.txt'
        checksums.write_text(sha(original) + '  ' + original.name + '\n' + (sha(package) + '  ' + package.name + '\n' if package != original else ''), encoding='utf-8')
        # Query destination and create only after size/integrity checks pass.
        try:
            target = api(GT, '/releases/tags/' + tag, gt_token)
        except SyncError as error:
            if 'HTTP 404;' not in str(error):
                raise
            notes = ('国内下载：下载附件。ZIP附件请先解压，再运行其中的安装程序。\n安装程序与GitHub原版逐字节一致，SHA256.txt同时列出安装程序与ZIP校验值。\n\n' + release.get('body', ''))
            target = api(GT, '/releases', gt_token, 'POST', {'tag_name': tag, 'target_commitish': 'main',
                'name': release['name'], 'body': notes, 'prerelease': release.get('prerelease', True)})
        if target.get('tag_name') != tag:
            raise SyncError('Destination release tag mismatch')
        ensure_asset(target['id'], package, gt_token, directory)
        ensure_asset(target['id'], checksums, gt_token, directory)
    # Re-read before updating: preserve concurrent newer release entries.
    manifest_entry = api(GH, '/contents/version.json', gh_token)
    manifest = json.loads(file_content(manifest_entry))
    latest = next(r for r in manifest['releases'] if r['version'] == tag[1:])
    if latest['sha256'] != row['sha256'] or latest['size_bytes'] != row['size_bytes']:
        raise SyncError('Source release changed during upload; refusing metadata update')
    latest['downloads']['gitee'] = DOMESTIC + '/tag/' + tag
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    readme = file_content(api(GH, '/contents/README.md', gh_token))
    # Gitee first: if it fails, GitHub does not advertise a successful mirror.
    put_file(GT, gt_token, 'README.md', readme)
    put_file(GT, gt_token, 'version.json', data)
    put_file(GH, gh_token, 'version.json', data, expected_sha=manifest_entry['sha'])
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    message = f'{tag}: Gitee package and checksums downloaded anonymously and verified; domestic update metadata published.\n'
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(message)
    print(message)

if __name__ == '__main__':
    try:
        main()
    except SyncError as error:
        print('ERROR: ' + str(error))
        raise SystemExit(1)
