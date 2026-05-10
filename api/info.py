from http.server import BaseHTTPRequestHandler
import json

def get_info_ytdlp(url):
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
                'player_skip': ['webpage'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get('formats', [])
    duration = info.get('duration', 0) or 0
    mins, secs = divmod(int(duration), 60)

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

    audio_formats = [
        f for f in formats
        if f.get('acodec') != 'none'
        and f.get('vcodec') == 'none'
        and f.get('url')
    ]
    best_audio = audio_formats[-1] if audio_formats else None

    return {
        'title': info.get('title', 'Video'),
        'channel': info.get('uploader', 'Unknown'),
        'duration': f'{mins}:{secs:02d}',
        'thumbnail': info.get('thumbnail', ''),
        'qualities': video_qualities[:6],
        'audio': {
            'url': best_audio['url'],
            'ext': best_audio.get('ext', 'm4a'),
        } if best_audio else None,
    }


def get_info_pytubefix(url):
    from pytubefix import YouTube

    yt = YouTube(url, use_po_token=True)

    streams_prog = yt.streams.filter(progressive=True).order_by('resolution').desc()
    streams_video = yt.streams.filter(adaptive=True, only_video=True).order_by('resolution').desc()
    stream_audio = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

    seen = set()
    video_qualities = []

    for s in list(streams_prog) + list(streams_video):
        res = s.resolution or ''
        if res in seen:
            continue
        seen.add(res)
        h = int(res.replace('p', '')) if res else 0
        label = '4K' if h >= 2160 else res
        video_qualities.append({
            'label': label,
            'height': h,
            'ext': s.subtype or 'mp4',
            'url': s.url,
            'filesize': s.filesize or 0,
        })

    video_qualities.sort(key=lambda x: x['height'], reverse=True)

    duration = yt.length or 0
    mins, secs = divmod(duration, 60)

    return {
        'title': yt.title,
        'channel': yt.author,
        'duration': f'{mins}:{secs:02d}',
        'thumbnail': yt.thumbnail_url,
        'qualities': video_qualities[:6],
        'audio': {
            'url': stream_audio.url,
            'ext': stream_audio.subtype or 'm4a',
        } if stream_audio else None,
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)
        url = data.get('url', '').strip()

        if not url:
            self._json(400, {'error': 'No URL provided'})
            return

        errors = []
        for fn in [get_info_ytdlp, get_info_pytubefix]:
            try:
                result = fn(url)
                self._json(200, result)
                return
            except Exception as e:
                errors.append(f'{fn.__name__}: {str(e)[:150]}')

        self._json(500, {'error': ' | '.join(errors)})

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
