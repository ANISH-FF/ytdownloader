from http.server import BaseHTTPRequestHandler
import json
import subprocess
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)
        url = data.get('url', '').strip()

        if not url:
            self._json(400, {'error': 'No URL provided'})
            return

        try:
            # Get video info + direct stream URLs via yt-dlp
            result = subprocess.run(
                [
                    'yt-dlp',
                    '--dump-json',
                    '--no-playlist',
                    url
                ],
                capture_output=True, text=True, timeout=25
            )

            if result.returncode != 0:
                self._json(500, {'error': result.stderr[:300] or 'Failed to fetch video info'})
                return

            info = json.loads(result.stdout)

            # Build quality options with direct URLs
            formats = info.get('formats', [])
            duration = info.get('duration', 0)
            mins, secs = divmod(int(duration), 60)

            # Pick best direct URLs per quality
            video_qualities = []
            seen = set()
            for f in reversed(formats):
                h = f.get('height')
                ext = f.get('ext', 'mp4')
                furl = f.get('url', '')
                if h and furl and h not in seen:
                    seen.add(h)
                    label = f"{h}p"
                    if h >= 2160: label = "4K"
                    video_qualities.append({
                        'label': label,
                        'height': h,
                        'ext': ext,
                        'url': furl,
                        'filesize': f.get('filesize') or f.get('filesize_approx') or 0,
                    })

            video_qualities.sort(key=lambda x: x['height'], reverse=True)

            # Best audio
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url')]
            best_audio = audio_formats[-1] if audio_formats else None

            self._json(200, {
                'title': info.get('title', 'Video'),
                'channel': info.get('uploader', 'Unknown'),
                'duration': f"{mins}:{secs:02d}",
                'thumbnail': info.get('thumbnail', ''),
                'qualities': video_qualities[:6],
                'audio': {
                    'url': best_audio['url'],
                    'ext': best_audio.get('ext', 'm4a'),
                } if best_audio else None,
            })

        except subprocess.TimeoutExpired:
            self._json(500, {'error': 'Timed out fetching info'})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
