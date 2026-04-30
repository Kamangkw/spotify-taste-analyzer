"""
Spotify Taste Analyzer v7 — Flask Backend
Signal/Noise · Mood Timeline · Taste Evolution · Compare Ranges · Calendar Heatmap · SVG Radar · Share Stats
"""
import os, re, time, math
from flask import Flask, render_template, jsonify, request
import urllib.request, urllib.parse, json
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# ── Genre → estimated audio features ─────────────────────────────
_GENRE_FEATURES = {
    'dance':       {'danceability': 0.85, 'energy': 0.75, 'valence': 0.75},
    'house':       {'danceability': 0.83, 'energy': 0.80, 'valence': 0.65},
    'techno':      {'danceability': 0.72, 'energy': 0.92, 'valence': 0.45},
    'edm':         {'danceability': 0.78, 'energy': 0.88, 'valence': 0.70},
    'electronic':  {'danceability': 0.75, 'energy': 0.82, 'valence': 0.58},
    'hip hop':     {'danceability': 0.80, 'energy': 0.70, 'valence': 0.65},
    'rap':         {'danceability': 0.78, 'energy': 0.68, 'valence': 0.60},
    'trap':        {'danceability': 0.75, 'energy': 0.80, 'valence': 0.45},
    'r&b':         {'danceability': 0.70, 'energy': 0.50, 'valence': 0.60},
    'soul':        {'danceability': 0.65, 'energy': 0.55, 'valence': 0.70},
    'indie':       {'danceability': 0.58, 'energy': 0.55, 'valence': 0.52},
    'rock':        {'danceability': 0.50, 'energy': 0.85, 'valence': 0.55},
    'alternative': {'danceability': 0.52, 'energy': 0.72, 'valence': 0.48},
    'metal':       {'danceability': 0.38, 'energy': 0.95, 'valence': 0.28},
    'punk':        {'danceability': 0.45, 'energy': 0.90, 'valence': 0.50},
    'pop':         {'danceability': 0.70, 'energy': 0.72, 'valence': 0.68},
    'k-pop':       {'danceability': 0.80, 'energy': 0.75, 'valence': 0.72},
    'jazz':        {'danceability': 0.45, 'energy': 0.40, 'valence': 0.65},
    'classical':   {'danceability': 0.28, 'energy': 0.22, 'valence': 0.55},
    'ambient':     {'danceability': 0.30, 'energy': 0.22, 'valence': 0.42},
    'lo-fi':       {'danceability': 0.72, 'energy': 0.40, 'valence': 0.55},
    'lofi':        {'danceability': 0.72, 'energy': 0.40, 'valence': 0.55},
    'chill':       {'danceability': 0.65, 'energy': 0.38, 'valence': 0.60},
    'acoustic':    {'danceability': 0.52, 'energy': 0.42, 'valence': 0.62},
    'folk':        {'danceability': 0.48, 'energy': 0.45, 'valence': 0.58},
    'country':     {'danceability': 0.55, 'energy': 0.58, 'valence': 0.62},
    'latin':       {'danceability': 0.78, 'energy': 0.72, 'valence': 0.72},
    'reggaeton':   {'danceability': 0.82, 'energy': 0.75, 'valence': 0.72},
    'japanese':    {'danceability': 0.65, 'energy': 0.68, 'valence': 0.60},
    'mandopop':    {'danceability': 0.68, 'energy': 0.62, 'valence': 0.65},
    'c-pop':       {'danceability': 0.70, 'energy': 0.65, 'valence': 0.68},
    'k-indie':     {'danceability': 0.60, 'energy': 0.50, 'valence': 0.55},
    'post-rock':   {'danceability': 0.35, 'energy': 0.65, 'valence': 0.35},
    'shoegaze':    {'danceability': 0.38, 'energy': 0.60, 'valence': 0.40},
    'dream pop':   {'danceability': 0.40, 'energy': 0.45, 'valence': 0.50},
    'synthwave':   {'danceability': 0.62, 'energy': 0.78, 'valence': 0.52},
    'vaporwave':   {'danceability': 0.55, 'energy': 0.35, 'valence': 0.45},
    'core':        {'danceability': 0.40, 'energy': 0.88, 'valence': 0.30},
    'garage':      {'danceability': 0.75, 'energy': 0.78, 'valence': 0.60},
    'uk garage':   {'danceability': 0.78, 'energy': 0.76, 'valence': 0.62},
    'grunge':      {'danceability': 0.45, 'energy': 0.82, 'valence': 0.38},
    'funk':        {'danceability': 0.80, 'energy': 0.72, 'valence': 0.78},
    'disco':       {'danceability': 0.85, 'energy': 0.78, 'valence': 0.80},
    'blues':       {'danceability': 0.52, 'energy': 0.48, 'valence': 0.55},
    'reggae':      {'danceability': 0.75, 'energy': 0.65, 'valence': 0.75},
    'dancehall':   {'danceability': 0.82, 'energy': 0.70, 'valence': 0.68},
    'afrobeats':   {'danceability': 0.80, 'energy': 0.72, 'valence': 0.78},
    'world':       {'danceability': 0.68, 'energy': 0.65, 'valence': 0.62},
    'soundtrack':  {'danceability': 0.35, 'energy': 0.45, 'valence': 0.50},
    'anime':       {'danceability': 0.68, 'energy': 0.72, 'valence': 0.65},
}

def estimate_features(genres):
    if not genres:
        return {'danceability': 0.55, 'energy': 0.58, 'valence': 0.50, 'tempo': 118}
    scores = {'danceability': 0, 'energy': 0, 'valence': 0}
    total_w = 0
    for genre, count in genres[:10]:
        genre_lower = genre.lower()
        w = count
        best_match, best_score = None, 0
        for g_name, g_feat in _GENRE_FEATURES.items():
            if g_name in genre_lower or genre_lower in g_name:
                if len(g_name) > best_score:
                    best_match, best_score = g_feat, len(g_name)
        if best_match:
            for k in scores:
                scores[k] += best_match[k] * w
            total_w += w
    if total_w == 0:
        return {'danceability': 0.55, 'energy': 0.58, 'valence': 0.50, 'tempo': 118}
    for k in scores:
        scores[k] = round(scores[k] / total_w, 3)
    scores['tempo'] = int(60 + scores['energy'] * 120)
    return scores

# ── Cache ────────────────────────────────────────────────────────
_CACHE = {}
_CACHE_TTL = 300

def cache_get(key):
    if key in _CACHE:
        val, ts = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return val, True
    return None, False

def cache_set(key, value):
    _CACHE[key] = (value, time.time())

# ── Token helpers ────────────────────────────────────────────────
def read_tokens():
    client_id     = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    access_token  = os.environ.get('SPOTIFY_ACCESS_TOKEN')
    if not client_id:
        try:
            with open('/opt/data/.env', 'rb') as f:
                raw = f.read()
            client_id     = re.search(b'SPOTIFY_CLIENT_ID=([a-zA-Z0-9]+)', raw).group(1).decode()
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

def api_get(url, cache_key=None):
    if cache_key:
        val, fresh = cache_get(cache_key)
        if fresh:
            return val
    token = get_access_token()
    req = urllib.request.Request(url, headers={'Authorization': f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if cache_key:
        cache_set(cache_key, data)
    return data

# ── Analysis helpers ─────────────────────────────────────────────

def signal_noise(top_tracks, top_artists):
    artist_pop_map = {a['id']: a.get('popularity', 0) for a in top_artists}
    signal_tracks, noise_tracks = [], []
    for i, track in enumerate(top_tracks[:30]):
        pop = track.get('popularity', 0)
        rank = i + 1
        artist_pop = 0
        for a in track.get('artists', []):
            artist_pop = max(artist_pop, artist_pop_map.get(a.get('id', ''), 0))
        avg_pop = (pop + artist_pop) // 2
        if avg_pop < 50 and rank <= 15:
            signal_tracks.append((track, avg_pop, rank))
        elif avg_pop > 75 and pop > 70 and rank > 10:
            noise_tracks.append((track, avg_pop, rank))
    signal_tracks.sort(key=lambda x: x[2])
    noise_tracks.sort(key=lambda x: x[1], reverse=True)
    return signal_tracks[:5], noise_tracks[:5]

def mood_timeline(recent_items):
    hour_moods = {
        range(5, 8):   {'label': 'Early Bird',  'emoji': '🌅', 'icon': '早晨啟動'},
        range(8, 12):  {'label': 'Focus Mode',  'emoji': '💼', 'icon': '工作/學習'},
        range(12, 14): {'label': 'Lunch Break', 'emoji': '☀️', 'icon': '午餐時光'},
        range(14, 18): {'label': 'Afternoon',   'emoji': '📖', 'icon': '下午時段'},
        range(18, 21): {'label': 'Wind Down',   'emoji': '🌆', 'icon': '收工放鬆'},
        range(21, 24): {'label': 'Night Vibes', 'emoji': '🌙', 'icon': '夜貓時間'},
        range(0, 5):   {'label': 'Late Night',  'emoji': '🌃', 'icon': '深夜時分'},
    }
    hour_count = {}
    for item in recent_items:
        try:
            h = int(item.get('played_at', '')[11:13])
        except Exception:
            continue
        for r, mood in hour_moods.items():
            if h in r:
                hour_count[mood['label']] = hour_count.get(mood['label'], 0) + 1
                break
    if not hour_count:
        return []
    max_c = max(hour_count.values())
    result = []
    for r, mood in hour_moods.items():
        label = mood['label']
        if label in hour_count:
            result.append({
                'label': label, 'emoji': mood['emoji'], 'icon': mood['icon'],
                'count': hour_count[label], 'pct': round(hour_count[label] / max_c * 100),
            })
    result.sort(key=lambda x: x['count'], reverse=True)
    return result

def listening_streak(recent_items):
    try:
        days = set()
        for item in recent_items:
            day = item.get('played_at', '')[:10]
            if day:
                days.add(day)
        day_list = sorted(days)
        if len(day_list) < 2:
            return {'days': len(day_list), 'streak': 1, 'status': '開始建立聆聽習慣'}
        today = datetime.utcnow().date()
        streak = 0
        check = today
        for d in reversed(day_list):
            day_dt = datetime.strptime(d, '%Y-%m-%d').date()
            if day_dt == check or day_dt == check - timedelta(days=1):
                streak += 1
                check = day_dt
            else:
                break
        if streak >= 7:   status = '🎉 音樂狂人！連續聆聽習慣超強'
        elif streak >= 4: status = '💪 穩定聆聽者'
        elif streak >= 2: status = '📈 正在建立習慣'
        else:             status = '🌱 剛開始探索'
        return {'days': len(day_list), 'streak': streak, 'status': status}
    except Exception:
        return {'days': 0, 'streak': 0, 'status': ''}

def calendar_heatmap(recent_items):
    """Build a 28-day listening heatmap from recent plays."""
    heatmap = {}  # date -> count
    now = datetime.utcnow()
    for i in range(28):
        day = (now - timedelta(days=i)).strftime('%Y-%m-%d')
        heatmap[day] = 0
    for item in recent_items:
        day = item.get('played_at', '')[:10]
        if day in heatmap:
            heatmap[day] += 1
    # Normalize to 0-4 level
    max_val = max(heatmap.values()) if heatmap.values() else 1
    result = []
    for day, count in sorted(heatmap.items()):
        level = int(count / max_val * 4) if max_val > 0 else 0
        date_obj = datetime.strptime(day, '%Y-%m-%d')
        result.append({
            'date': day,
            'day': date_obj.strftime('%a'),
            'daynum': date_obj.day,
            'count': count,
            'level': level,
        })
    return result

def top_collaborators(top_artists):
    """Find most frequent collaborators across top tracks."""
    return []  # computed inline in route

def taste_evolution(current_range):
    """Compare current time range with other ranges to detect shifts."""
    ranges = ['short_term', 'medium_term', 'long_term']
    other_ranges = [r for r in ranges if r != current_range]
    evolution = {}
    # Fetch other range top artists/genres
    for r in other_ranges:
        ck = f'top_genres_{r}'
        val, fresh = cache_get(ck)
        if not fresh:
            data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={r}', cache_key=f'top_artists_{r}')
            genre_count = {}
            for a in data['items']:
                for g in a.get('genres', []):
                    genre_count[g] = genre_count.get(g, 0) + 1
            sorted_g = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
            cache_set(f'top_genres_{r}', sorted_g[:20])
            val = sorted_g[:20]
        evolution[r] = val
    return evolution

def build_share_text(top_artists, top_tracks, top_genres, features, stats, taste_profile, streak):
    """Build a plain-text shareable summary."""
    top_artist_name = top_artists[0]['name'] if top_artists else '?'
    top_genre_name = top_genres[0][0] if top_genres else '?'
    lines = [
        "🎵 我的 Spotify 品味分析",
        f"Profile: {taste_profile}",
        f"Top Artist: {top_artist_name}",
        f"Top Genre: {top_genre_name}",
        f"Avg BPM: {features['tempo']} | Dance: {int(features['danceability']*100)}% | Energy: {int(features['energy']*100)}%",
        f"Top Tracks Duration: {stats['duration']}min",
        f"聆聽習慣: {streak['status']}",
    ]
    return '\n'.join(lines)

# ── Routes ───────────────────────────────────────────────────────

app.jinja_env.globals['now'] = lambda: datetime.now().strftime('%Y-%m-%d')

@app.route('/')
def index():
    try:
        time_range = request.args.get('range', 'medium_term')
        token = get_access_token()

        top_artists_data = api_get(
            f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={time_range}',
            cache_key=f'top_artists_{time_range}'
        )
        top_tracks_data = api_get(
            f'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={time_range}',
            cache_key=f'top_tracks_{time_range}'
        )
        recent_raw = api_get(
            'https://api.spotify.com/v1/me/player/recently-played?limit=50',
            cache_key='recent_50'
        )

        top_artists = top_artists_data['items']
        top_tracks  = top_tracks_data['items']
        recent_items = recent_raw['items']

        # Genre dist
        genre_count = {}
        for artist in top_artists:
            for g in artist.get('genres', []):
                genre_count[g] = genre_count.get(g, 0) + 1
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        top_genres = [(g, c) for g, c in sorted_genres if c >= 2]

        # Decade dist
        decade_count = {'2020s': 0, '2010s': 0, '2000s': 0, '1990s': 0, '1980s': 0, 'Earlier': 0}
        for track in top_tracks:
            year = track.get('album', {}).get('release_date', '0000')[:4]
            d = int(year) if year.isdigit() else 0
            if d >= 2020:   decade_count['2020s'] += 1
            elif d >= 2010: decade_count['2010s'] += 1
            elif d >= 2000: decade_count['2000s'] += 1
            elif d >= 1990: decade_count['1990s'] += 1
            elif d >= 1980: decade_count['1980s'] += 1
            else:           decade_count['Earlier'] += 1
        sorted_decades = sorted(decade_count.items(), key=lambda x: x[1], reverse=True)
        top_decades = [(d, c) for d, c in sorted_decades if c > 0]

        # Listening time
        hour_buckets = {'Morning (6-12)': 0, 'Afternoon (12-18)': 0, 'Evening (18-24)': 0, 'Night (0-6)': 0}
        for item in recent_items:
            try:
                h = int(item.get('played_at', '')[11:13])
            except Exception:
                continue
            if 6 <= h < 12:    hour_buckets['Morning (6-12)'] += 1
            elif 12 <= h < 18: hour_buckets['Afternoon (12-18)'] += 1
            elif 18 <= h < 24: hour_buckets['Evening (18-24)'] += 1
            else:              hour_buckets['Night (0-6)'] += 1
        sorted_hours = sorted(hour_buckets.items(), key=lambda x: x[1], reverse=True)

        features = estimate_features(top_genres)
        signal_tracks, noise_tracks = signal_noise(top_tracks, top_artists)
        mood_data = mood_timeline(recent_items)
        streak = listening_streak(recent_items)
        heatmap = calendar_heatmap(recent_items)

        # Top collaborators (artists that appear most across your top tracks)
        artist_track_count = {}
        for track in top_tracks:
            for a in track.get('artists', []):
                aid = a['id']
                if aid not in artist_track_count:
                    artist_track_count[aid] = {'name': a['name'], 'count': 0, 'images': a.get('images', [])}
                artist_track_count[aid]['count'] += 1
        top_collab = sorted(artist_track_count.values(), key=lambda x: x['count'], reverse=True)[:10]

        # Share text
        share_text = build_share_text(top_artists, top_tracks, top_genres, features,
            {'duration': round(sum(t.get('duration_ms', 0) for t in top_tracks) / 60000)},
            '多元品味', streak)

        # Taste profile
        energy = features['energy']
        dance  = features['danceability']
        valence = features['valence']
        if energy > 0.75 and dance > 0.7:
            taste_profile = "⚡ 派對動物 — 高能量舞曲愛好者"
        elif energy > 0.65 and valence > 0.6:
            taste_profile = "🌴 陽光系 — 正面能量音樂粉"
        elif energy < 0.45 and dance < 0.55:
            taste_profile = "🌙 沉思者 — 偏好內斂低沉氛圍"
        elif dance > 0.72:
            taste_profile = "💃 節奏控 — 跟著節拍走"
        elif valence < 0.4:
            taste_profile = "🥀 憂傷美學 — 暗黑系音樂愛好者"
        else:
            taste_profile = "🎭 多元品味 — 唔被單一風格定義"

        # Stats
        total_tracks = len(top_tracks)
        explicit_count = sum(1 for t in top_tracks if t.get('explicit'))
        avg_popularity = round(sum(t.get('popularity', 0) for t in top_tracks) / max(total_tracks, 1))
        total_duration_min = round(sum(t.get('duration_ms', 0) for t in top_tracks) / 60000)

        return render_template(
            'index.html',
            top_artists=top_artists,
            top_tracks=top_tracks,
            recent=recent_items[:20],
            top_genres=top_genres,
            top_decades=top_decades,
            features=features,
            time_range=time_range,
            sorted_hours=sorted_hours,
            discovery_genres=top_genres[:12],
            signal_tracks=[s[0] for s in signal_tracks],
            noise_tracks=[n[0] for n in noise_tracks],
            mood_data=mood_data,
            streak=streak,
            heatmap=heatmap,
            top_collab=top_collab,
            share_text=share_text,
            taste_profile=taste_profile,
            stats={
                'explicit': explicit_count,
                'popularity': avg_popularity,
                'duration': total_duration_min,
                'genres': len(top_genres),
            },
        )
    except Exception as e:
        import traceback
        return f"<pre>Error: {e}\n\n{traceback.format_exc()}</pre>", 500

@app.route('/api/top-artists')
def api_top_artists():
    t = request.args.get('time_range', 'medium_term')
    data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={t}', cache_key=f'top_artists_{t}')
    return jsonify(data['items'])

@app.route('/api/top-tracks')
def api_top_tracks():
    t = request.args.get('time_range', 'medium_term')
    data = api_get(f'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={t}', cache_key=f'top_tracks_{t}')
    return jsonify(data['items'])

@app.route('/api/recent')
def api_recent():
    data = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50', cache_key='recent_50')
    return jsonify(data['items'])

@app.route('/api/compare-ranges')
def api_compare_ranges():
    """Compare all 3 time ranges: genre shifts, new artists, genre evolution."""
    try:
        ranges = {
            'short_term': '4週',
            'medium_term': '6個月',
            'long_term': 'All Time',
        }
        result = {}
        all_genres = {}  # genre -> {short: count, medium: count, long: count}
        all_artist_ids = {}  # artist_id -> {name, short_rank, medium_rank, long_rank}

        for r in ranges:
            data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={r}', cache_key=f'top_artists_{r}')
            for i, artist in enumerate(data['items']):
                aid = artist['id']
                if aid not in all_artist_ids:
                    all_artist_ids[aid] = {'name': artist['name'], 'genres': artist.get('genres', []), 'images': artist.get('images', [])}
                all_artist_ids[aid][f'{r}_rank'] = i + 1
                for g in artist.get('genres', []):
                    if g not in all_genres:
                        all_genres[g] = {'short': 0, 'medium': 0, 'long': 0}
                    all_genres[g][r] = all_genres[g].get(r, 0) + 1

        # Genre shifts: rising vs declining
        genre_shifts = []
        for g, counts in all_genres.items():
            s = counts.get('short', 0)
            m = counts.get('medium', 0)
            l = counts.get('long', 0)
            total = s + m + l
            if total < 3:
                continue
            # Rising = short > medium > long (recently increased)
            if s > m > l or s > m and l < m:
                genre_shifts.append({'genre': g, 'direction': 'rising', 'short': s, 'medium': m, 'long': l})
            # Declining = long > medium > short (was more popular before)
            elif l > m > s or l > m and s < m:
                genre_shifts.append({'genre': g, 'direction': 'declining', 'short': s, 'medium': m, 'long': l})
        genre_shifts.sort(key=lambda x: x['short'], reverse=True)
        rising = [g for g in genre_shifts if g['direction'] == 'rising'][:5]
        declining = [g for g in genre_shifts if g['direction'] == 'declining'][:5]

        # Top artists per range
        top_per_range = {}
        for r in ranges:
            data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=10&time_range={r}', cache_key=f'top_artists_{r}')
            top_per_range[r] = [{'name': a['name'], 'id': a['id'], 'genres': a.get('genres', [])[:2]} for a in data['items']]

        return jsonify({
            'rising_genres': rising,
            'declining_genres': declining,
            'top_per_range': top_per_range,
            'range_labels': ranges,
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/calendar')
def api_calendar():
    try:
        data = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50', cache_key='recent_50')
        heatmap = calendar_heatmap(data['items'])
        return jsonify(heatmap)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh-token')
def api_refresh():
    try:
        tokens = read_tokens()
        new_token = refresh_access_token(
            tokens['client_id'], tokens['client_secret'], tokens['refresh_token']
        )
        return jsonify({'success': True, 'token': new_token[:20] + '...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
