from http.server import BaseHTTPRequestHandler
import json
import yt_dlp

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
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'noplaylist': True,
                'format': 'bestvideo+bestaudio/best',
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = info.get('formats', [])
            duration = info.get('duration', 0) or 0
            mins, secs = divmod(int(duration), 60)

            # Pick best stream per height (prefer mp4/webm with both video+audio)
            video_qualities = []
            seen = set()
            for f in reversed(formats):
                h = f.get('height')
                furl = f.get('url', '')
                vcodec = f.get('vcodec', 'none')
                ext = f.get('ext', 'mp4')
                if h and furl and vcodec != 'none' and h not in seen:
                    seen.add(h)
                    label = '4K' if h >= 2160 else f'{h}p'
                    video_qualities.append({
                        'label': label,
                        'height': h,
                        'ext': ext,
                        'url': furl,
                        'filesize': f.get('filesize') or f.get('filesize_approx') or 0,
                    })

            video_qualities.sort(key=lambda x: x['height'], reverse=True)

            # Best audio-only stream
            audio_formats = [
                f for f in formats
                if f.get('acodec') != 'none'
                and f.get('vcodec') == 'none'
                and f.get('url')
            ]
            best_audio = audio_formats[-1] if audio_formats else None

            self._json(200, {
                'title': info.get('title', 'Video'),
                'channel': info.get('uploader', 'Unknown'),
                'duration': f'{mins}:{secs:02d}',
                'thumbnail': info.get('thumbnail', ''),
                'qualities': video_qualities[:6],
                'audio': {
                    'url': best_audio['url'],
                    'ext': best_audio.get('ext', 'm4a'),
                } if best_audio else None,
            })

        except Exception as e:
            self._json(500, {'error': str(e)[:300]})

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
