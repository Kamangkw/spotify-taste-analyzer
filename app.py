"""
Spotify Taste Analyzer — Flask Backend
"""
import os, re, math
from flask import Flask, render_template, jsonify, request
import urllib.request, urllib.parse, json
from datetime import datetime

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# ── Token helpers ────────────────────────────────────────────────

def read_tokens():
    """Read tokens from environment variables (Render) or local .env (dev)."""
    client_id     = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    access_token  = os.environ.get('SPOTIFY_ACCESS_TOKEN')
    if not client_id:
        try:
            with open('/opt/data/.env', 'rb') as f:
                raw = f.read()
            client_id     = re.search(b'SPOTIFY_CLIENT_ID=([a-zA-Z0-9]+)',     raw).group(1).decode()
            client_secret = re.search(b'SPOTIFY_CLIENT_SECRET=([a-zA-Z0-9]+)', raw).group(1).decode()
            refresh_token = re.search(b'SPOTIFY_REFRESH_TOKEN=([A-Za-z0-9_-]+)', raw).group(1).decode()
            access        = re.search(b'SPOTIFY_ACCESS_TOKEN=([A-Za-z0-9_-]+)', raw)
            access_token  = access.group(1).decode() if access else None
        except Exception:
            pass
    if not client_id:
        raise Exception("Spotify credentials not found")
    return {'client_id': client_id, 'client_secret': client_secret,
            'refresh_token': refresh_token, 'access_token': access_token}

def refresh_access_token(client_id, client_secret, refresh_token):
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token', 'refresh_token': refresh_token,
        'client_id': client_id, 'client_secret': client_secret,
    }).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())['access_token']

def get_access_token():
    tokens = read_tokens()
    try:
        req = urllib.request.Request(
            'https://api.spotify.com/v1/me/top/artists?limit=1',
            headers={'Authorization': f"Bearer {tokens['access_token']}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return tokens['access_token']
    except Exception:
        new_token = refresh_access_token(
            tokens['client_id'], tokens['client_secret'], tokens['refresh_token']
        )
        return new_token

def api_get(url):
    token = get_access_token()
    req = urllib.request.Request(url, headers={'Authorization': f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

# ── Helper: parse listening time ────────────────────────────────

def parse_hour(iso_str):
    try:
        return int(iso_str[11:13])
    except Exception:
        return None

# ── Routes ───────────────────────────────────────────────────────

app.jinja_env.globals['now'] = lambda: datetime.now().strftime('%Y-%m-%d')

@app.route('/')
def index():
    try:
        time_range = request.args.get('range', 'medium_term')
        token = get_access_token()

        top_artists = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={time_range}')
        top_tracks  = api_get(f'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={time_range}')
        recent_raw  = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50')

        # ── Genre distribution ─────────────────────────────────
        genre_count = {}
        for artist in top_artists['items']:
            for g in artist.get('genres', []):
                genre_count[g] = genre_count.get(g, 0) + 1
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        top_genres = [(g, c) for g, c in sorted_genres if c >= 2]

        # ── Decade distribution ──────────────────────────────
        decade_count = {'2020s': 0, '2010s': 0, '2000s': 0, '1990s': 0, '1980s': 0, 'Earlier': 0}
        for track in top_tracks['items']:
            year = track.get('album', {}).get('release_date', '0000')[:4]
            d = int(year) if year.isdigit() else 0
            if d >= 2020: decade_count['2020s'] += 1
            elif d >= 2010: decade_count['2010s'] += 1
            elif d >= 2000: decade_count['2000s'] += 1
            elif d >= 1990: decade_count['1990s'] += 1
            elif d >= 1980: decade_count['1980s'] += 1
            else: decade_count['Earlier'] += 1
        sorted_decades = sorted(decade_count.items(), key=lambda x: x[1], reverse=True)
        top_decades = [(d, c) for d, c in sorted_decades if c > 0]

        # ── Listening time distribution ──────────────────────
        hour_buckets = {'Morning (6-12)': 0, 'Afternoon (12-18)': 0, 'Evening (18-24)': 0, 'Night (0-6)': 0}
        for item in recent_raw['items']:
            h = parse_hour(item.get('played_at', ''))
            if h is not None:
                if 6 <= h < 12:   hour_buckets['Morning (6-12)'] += 1
                elif 12 <= h < 18: hour_buckets['Afternoon (12-18)'] += 1
                elif 18 <= h < 24: hour_buckets['Evening (18-24)'] += 1
                else:              hour_buckets['Night (0-6)'] += 1
        sorted_hours = sorted(hour_buckets.items(), key=lambda x: x[1], reverse=True)

        # ── Discovery Radar (Recommendations) ────────────────
        top_artist_ids = [a['id'] for a in top_artists['items'][:5]]
        top_genre_list = [g for g, c in sorted_genres[:5]]
        discovery_tracks = []
        if top_artist_ids:
            seed_str = ','.join(top_artist_ids[:2])
            try:
                recs = api_get(f'https://api.spotify.com/v1/recommendations?seed_artists={seed_str}&limit=8&market=HK')
                discovery_tracks = recs.get('tracks', [])[:8]
            except Exception:
                pass

        # ── Listening stats ─────────────────────────────────
        total_tracks = len(top_tracks['items'])
        explicit_count = sum(1 for t in top_tracks['items'] if t.get('explicit'))
        avg_popularity = round(sum(t.get('popularity', 0) for t in top_tracks['items']) / max(total_tracks, 1))
        total_duration_ms = sum(t.get('duration_ms', 0) for t in top_tracks['items'])
        total_duration_min = round(total_duration_ms / 60000)

        # Placeholder audio features
        features = {'danceability': 0.55, 'energy': 0.58, 'valence': 0.50, 'tempo': 118}

        return render_template(
            'index.html',
            top_artists=top_artists['items'],
            top_tracks=top_tracks['items'],
            recent=recent_raw['items'][:20],
            top_genres=top_genres,
            top_decades=top_decades,
            features=features,
            time_range=time_range,
            sorted_hours=sorted_hours,
            discovery_tracks=discovery_tracks,
            stats={
                'explicit': explicit_count,
                'popularity': avg_popularity,
                'duration': total_duration_min,
            },
        )
    except Exception as e:
        import traceback
        return f"<pre>Error: {e}\n\n{traceback.format_exc()}</pre>", 500

@app.route('/api/top-artists')
def api_top_artists():
    time = request.args.get('time_range', 'medium_term')
    data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={time}')
    return jsonify(data['items'])

@app.route('/api/top-tracks')
def api_top_tracks():
    time = request.args.get('time_range', 'medium_term')
    data = api_get(f'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={time}')
    return jsonify(data['items'])

@app.route('/api/recent')
def api_recent():
    data = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50')
    return jsonify(data['items'])

@app.route('/api/discovery')
def api_discovery():
    """Get personalized recommendations based on top artists."""
    try:
        top_artists = api_get('https://api.spotify.com/v1/me/top/artists?limit=5')
        top_genres  = api_get('https://api.spotify.com/v1/me/top/artists?limit=20')
        genre_count = {}
        for a in top_genres['items']:
            for g in a.get('genres', []):
                genre_count[g] = genre_count.get(g, 0) + 1
        top_g = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        genre_seeds = ','.join([g for g, c in top_g[:2]])
        artist_ids = [a['id'] for a in top_artists['items'][:3]]
        artist_seeds = ','.join(artist_ids[:2])
        url = f'https://api.spotify.com/v1/recommendations?seed_artists={artist_seeds}&seed_genres={genre_seeds}&limit=10&market=HK'
        recs = api_get(url)
        return jsonify(recs.get('tracks', []))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
