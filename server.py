#!/usr/bin/env python3
"""Loopback-only dashboard for the existing local reel generator."""
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / 'logs' / 'jobs'
LOCK = threading.Lock()
ACTIVE = None


def library():
    records = {}
    history = ROOT / 'logs' / 'history.jsonl'
    for line in history.read_text().splitlines() if history.exists() else []:
        try:
            info = json.loads(line)
            path = Path(info['video']).resolve()
            if path.parent not in (ROOT / 'output', Path.home() / 'Downloads'):
                continue
            info['id'] = path.stem
            info['available'] = path.is_file()
            records[path.stem] = info
        except (ValueError, KeyError, TypeError):
            continue
    return list(reversed(list(records.values())))


def read_job(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def save_job(job):
    path = JOBS / (job['id'] + '.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(job))
    temporary.replace(path)


def run_job(job):
    global ACTIVE
    try:
        log_path = JOBS / (job['id'] + '.log')
        env = os.environ.copy()
        env['PATH'] = '/opt/homebrew/bin:' + env.get('PATH', '')
        with log_path.open('w') as log:
            script = 'generate_youtube.py' if job.get('format') == 'youtube' else 'generate.py'
            command = [
                str(ROOT / '.venv/bin/python'), '-u', str(ROOT / script),
                '--topic', job['topic'], '--mood', job['mood'],
                '--reel-type', job.get('reel_type', 'motivation'),
                '--output-dir', str(ROOT / 'output'),
            ]
            if script == 'generate.py':
                command.extend(['--visuals', job['visuals']])
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        job['status'] = 'complete' if result.returncode == 0 else 'failed'
        if result.returncode == 0:
            lines = log_path.read_text(errors='replace').splitlines()
            video = next((line[7:] for line in reversed(lines) if line.startswith('Video: ')), '')
            job['reel_id'] = Path(video).stem
    except Exception as exc:
        job.update(status='failed', error=str(exc))
    finally:
        save_job(job)
        with LOCK:
            ACTIVE = None


class Handler(BaseHTTPRequestHandler):
    def json_response(self, data, status=200):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.valid_host():
            return self.json_response({'error': 'Invalid host'}, 403)
        path = urlsplit(self.path).path
        if path == '/api/state':
            jobs = []
            for file in sorted(JOBS.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                job = read_job(file)
                if job:
                    log = file.with_suffix('.log')
                    job['log'] = log.read_text(errors='replace')[-16000:] if log.exists() else ''
                    jobs.append(job)
            return self.json_response({'reels': library(), 'jobs': jobs})
        if path.startswith('/media/'):
            parts = path.split('/')
            if len(parts) != 4 or parts[3] not in ('video', 'metadata', 'caption', 'script'):
                return self.send_error(404)
            info = next((r for r in library() if r['id'] == parts[2]), None)
            if not info:
                return self.send_error(404)
            file = Path(info['video']).resolve().with_suffix({'video': '.mp4', 'metadata': '.json', 'caption': '.txt', 'script': '.script.txt'}[parts[3]])
            return self.send_file(file, download=parts[3] != 'video' or 'download' in urlsplit(self.path).query)
        assets = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if path in assets:
            return self.send_file(ROOT / 'ui' / assets[path])
        self.send_error(404)

    def send_file(self, path, download=False):
        if not path.is_file():
            return self.send_error(404)
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', range_header)
            if not match:
                return self.send_error(416)
            start = int(match[1])
            end = min(int(match[2]) if match[2] else end, end)
            if start > end:
                return self.send_error(416)
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if range_header:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.end_headers()
        try:
            with path.open('rb') as file:
                file.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = file.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        global ACTIVE
        if not self.valid_host() or self.headers.get('Origin') not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.json_response({'error': 'Invalid origin'}, 403)
        if self.path != '/api/generate':
            return self.send_error(404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(length))
            video_format = data.get('format', 'reel')
            if not isinstance(video_format, str) or video_format not in ('reel', 'youtube'):
                raise ValueError('Invalid video format')
            if video_format == 'youtube' and data.get('visuals') != 'ai':
                raise ValueError('YouTube videos require AI images')
            reel_type = data.get('reel_type', 'motivation')
            if not isinstance(reel_type, str) or reel_type not in ('motivation', 'love', 'buddhism', 'true_events', 'city'):
                raise ValueError('Invalid reel type')
            if reel_type == 'city' and data.get('visuals') != 'ai':
                raise ValueError('City reels require AI images')
            topic = data.get('topic', '')
            if not isinstance(topic, str) or len(topic) > 500:
                raise ValueError('Theme must be at most 500 characters')
            if data.get('mood') not in ('auto', 'calm', 'build', 'epic') or data.get('visuals') not in ('ai', 'footage'):
                raise ValueError('Invalid generation options')
        except (ValueError, AttributeError):
            return self.json_response({'error': 'Invalid generation options'}, 400)
        with LOCK:
            if ACTIVE:
                return self.json_response({'error': 'A video is already generating'}, 409)
            job = {'id': uuid.uuid4().hex, 'status': 'running', 'topic': topic.strip(), 'reel_type': reel_type, 'format': video_format, 'mood': data['mood'], 'visuals': data['visuals']}
            save_job(job)
            ACTIVE = job['id']
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
        return self.json_response(job, 202)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    JOBS.mkdir(parents=True, exist_ok=True)
    for file in JOBS.glob('*.json'):
        job = read_job(file)
        if job and job['status'] == 'running':
            job.update(status='failed', error='Server stopped during generation. You can generate again.')
            save_job(job)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Motivation Studio: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
