"""
Spotify Taste Analyzer — Flask Backend
"""
import os
import re
import math
from flask import Flask, render_template, jsonify, request
import urllib.request
import urllib.parse
import json
from datetime import datetime

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# ── Token helpers ────────────────────────────────────────────────

def read_tokens():
    """Read tokens from environment variables (Render) or local .env (dev)."""
    # Try Render environment variables first
    client_id     = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    access_token  = os.environ.get('SPOTIFY_ACCESS_TOKEN')

    # Fall back to local .env (for local dev only)
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
        raise Exception("Spotify credentials not found in environment or .env")
    return {'client_id': client_id, 'client_secret': client_secret,
            'refresh_token': refresh_token, 'access_token': access_token}

def refresh_access_token(client_id, client_secret, refresh_token):
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    }).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    return result['access_token']

def get_access_token():
    tokens = read_tokens()
    try:
        # Try existing token by calling a lightweight API
        req = urllib.request.Request(
            'https://api.spotify.com/v1/me/top/artists?limit=1',
            headers={'Authorization': f"Bearer {tokens['access_token']}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return tokens['access_token']
    except Exception:
        # Token expired — refresh
        new_token = refresh_access_token(
            tokens['client_id'], tokens['client_secret'], tokens['refresh_token']
        )
        # Save back (partial save — update .env in memory only)
        return new_token

def api_get(url):
    """GET Spotify API with fresh token."""
    token = get_access_token()
    req = urllib.request.Request(url, headers={'Authorization': f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

# ── Routes ───────────────────────────────────────────────────────

app.jinja_env.globals['now'] = lambda: datetime.now().strftime('%Y-%m-%d')

@app.route('/')
def index():
    """Main taste overview dashboard."""
    try:
        token = get_access_token()

        # Fetch all data
        top_artists = api_get('https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term')
        top_tracks  = api_get('https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term')
        recent      = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50')

        # ── Genre distribution ──────────────────────────────────────
        genre_count = {}
        for artist in top_artists['items']:
            for g in artist.get('genres', []):
                genre_count[g] = genre_count.get(g, 0) + 1
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        top_genres = [(g, c) for g, c in sorted_genres if c >= 2]

        # ── Decade distribution (from top tracks) ─────────────────
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

        # ── Audio feature averages ───────────────────────────────
        # Note: /audio-features requires additional scopes, skip for now
        features = {'danceability': 0.5, 'energy': 0.5, 'valence': 0.5, 'tempo': 120}

        return render_template(
            'index.html',
            top_artists=top_artists['items'],
            top_tracks=top_tracks['items'],
            recent=recent['items'][:20],
            top_genres=top_genres,
            top_decades=top_decades,
            features=features,
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

@app.route('/api/audio-features/<track_ids>')
def api_audio_features(track_ids):
    data = api_get(f'https://api.spotify.com/v1/audio-features?ids={track_ids}')
    return jsonify(data.get('audio_features', []))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
