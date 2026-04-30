"""
Spotify Taste Analyzer v9 — Flask Backend
Artist Connection Web · Taste DNA · Decade Breakdown · Peak Hours
"""
import os, re, time
from flask import Flask, render_template, jsonify, request
import urllib.request, urllib.parse, json
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

_GENRE_FEATURES = {
    'dance':{'danceability':0.85,'energy':0.75,'valence':0.75},'house':{'danceability':0.83,'energy':0.80,'valence':0.65},
    'techno':{'danceability':0.72,'energy':0.92,'valence':0.45},'edm':{'danceability':0.78,'energy':0.88,'valence':0.70},
    'electronic':{'danceability':0.75,'energy':0.82,'valence':0.58},'hip hop':{'danceability':0.80,'energy':0.70,'valence':0.65},
    'rap':{'danceability':0.78,'energy':0.68,'valence':0.60},'trap':{'danceability':0.75,'energy':0.80,'valence':0.45},
    'r&b':{'danceability':0.70,'energy':0.50,'valence':0.60},'soul':{'danceability':0.65,'energy':0.55,'valence':0.70},
    'indie':{'danceability':0.58,'energy':0.55,'valence':0.52},'rock':{'danceability':0.50,'energy':0.85,'valence':0.55},
    'alternative':{'danceability':0.52,'energy':0.72,'valence':0.48},'metal':{'danceability':0.38,'energy':0.95,'valence':0.28},
    'punk':{'danceability':0.45,'energy':0.90,'valence':0.50},'pop':{'danceability':0.70,'energy':0.72,'valence':0.68},
    'k-pop':{'danceability':0.80,'energy':0.75,'valence':0.72},'jazz':{'danceability':0.45,'energy':0.40,'valence':0.65},
    'classical':{'danceability':0.28,'energy':0.22,'valence':0.55},'ambient':{'danceability':0.30,'energy':0.22,'valence':0.42},
    'lo-fi':{'danceability':0.72,'energy':0.40,'valence':0.55},'lofi':{'danceability':0.72,'energy':0.40,'valence':0.55},
    'chill':{'danceability':0.65,'energy':0.38,'valence':0.60},'acoustic':{'danceability':0.52,'energy':0.42,'valence':0.62},
    'folk':{'danceability':0.48,'energy':0.45,'valence':0.58},'latin':{'danceability':0.78,'energy':0.72,'valence':0.72},
    'reggaeton':{'danceability':0.82,'energy':0.75,'valence':0.72},'japanese':{'danceability':0.65,'energy':0.68,'valence':0.60},
    'mandopop':{'danceability':0.68,'energy':0.62,'valence':0.65},'c-pop':{'danceability':0.70,'energy':0.65,'valence':0.68},
    'k-indie':{'danceability':0.60,'energy':0.50,'valence':0.55},'post-rock':{'danceability':0.35,'energy':0.65,'valence':0.35},
    'shoegaze':{'danceability':0.38,'energy':0.60,'valence':0.40},'dream pop':{'danceability':0.40,'energy':0.45,'valence':0.50},
    'synthwave':{'danceability':0.62,'energy':0.78,'valence':0.52},'vaporwave':{'danceability':0.55,'energy':0.35,'valence':0.45},
    'funk':{'danceability':0.80,'energy':0.72,'valence':0.78},'disco':{'danceability':0.85,'energy':0.78,'valence':0.80},
    'garage':{'danceability':0.75,'energy':0.78,'valence':0.60},'grunge':{'danceability':0.45,'energy':0.82,'valence':0.38},
    'blues':{'danceability':0.52,'energy':0.48,'valence':0.55},'reggae':{'danceability':0.75,'energy':0.65,'valence':0.75},
    'dancehall':{'danceability':0.82,'energy':0.70,'valence':0.68},'afrobeats':{'danceability':0.80,'energy':0.72,'valence':0.78},
    'anime':{'danceability':0.68,'energy':0.72,'valence':0.65},'soundtrack':{'danceability':0.35,'energy':0.45,'valence':0.50},
}

def estimate_features(genres):
    if not genres: return {'danceability':0.55,'energy':0.58,'valence':0.50,'tempo':118}
    scores = {'danceability':0,'energy':0,'valence':0}; total_w = 0
    for genre, count in genres[:10]:
        g = genre.lower(); w = count; best, best_s = None, 0
        for n, f in _GENRE_FEATURES.items():
            if n in g or g in n:
                if len(n) > best_s: best, best_s = f, len(n)
        if best:
            for k in scores: scores[k] += best[k] * w
            total_w += w
    if total_w == 0: return {'danceability':0.55,'energy':0.58,'valence':0.50,'tempo':118}
    for k in scores: scores[k] = round(scores[k]/total_w, 3)
    scores['tempo'] = int(60 + scores['energy']*120)
    return scores

# ── Taste DNA ──────────────────────────────────────────
def taste_dna(top_artists, top_tracks, top_genres):
    """
    What defines your taste? 5 dimensions:
    - Groove (dance + funk + disco + soul)
    - Edge (punk + metal + core + noise)
    - Chill (ambient + lo-fi + chill + dream pop)
    - Pop (k-pop + j-pop + c-pop + mainstream)
    - Depth (classical + jazz + post-rock + shoegaze)
    """
    dim_scores = {'Groove':0,'Edge':0,'Chill':0,'Pop':0,'Depth':0}
    dim_genres = {
        'Groove':['dance','funk','disco','soul','r&b','groove','house','garage','uk garage','reggae','dancehall'],
        'Edge':['punk','metal','hardcore','core','grunge','noise','alternative rock','post-punk','industrial'],
        'Chill':['ambient','lo-fi','lofi','chill','chillwave','dream pop','shoegaze','post-rock','vaporwave','meditation'],
        'Pop':['pop','k-pop','j-pop','c-pop','mandopop','electropop','synthpop','teen pop','bubblegum pop'],
        'Depth':['classical','jazz','avant-garde','experimental','noise rock','black metal','doom','drone'],
    }
    for genre, count in top_genres[:15]:
        gl = genre.lower()
        for dim, keywords in dim_genres.items():
            if any(k in gl for k in keywords):
                dim_scores[dim] += count
    total = sum(dim_scores.values()) or 1
    result = []
    for dim, score in dim_scores.items():
        pct = round(score / total * 100)
        result.append({'dim': dim, 'pct': pct, 'raw': score})
    result.sort(key=lambda x: x['pct'], reverse=True)
    return result

# ── Decade Breakdown ─────────────────────────────────
def decade_breakdown(top_tracks):
    """More granular decade + half-decade analysis"""
    buckets = {}
    for t in top_tracks:
        yr_str = t.get('album',{}).get('release_date','0000')[:4]
        if not yr_str.isdigit(): continue
        yr = int(yr_str)
        half = 'a' if (yr % 10) < 5 else 'b'
        bucket = f"{(yr//10)*10}s{half}"  # e.g. "2010sa" = early 2010s, "2010sb" = late 2010s
        buckets[bucket] = buckets.get(bucket, 0) + 1
    # Human labels
    labels = {
        '2020sa':'2020 early','2020sb':'2020 late',
        '2010sa':'2010 early','2010sb':'2010 late',
        '2000sa':'2000 early','2000sb':'2000 late',
        '1990sa':'1990 early','1990sb':'1990 late',
        '1980sa':'1980 early','1980sb':'1980 late',
    }
    result = []
    for bucket, count in sorted(buckets.items(), key=lambda x: x[0], reverse=True):
        label = labels.get(bucket, bucket)
        yr = int(bucket[:4])
        age = datetime.now().year - yr
        result.append({'bucket':bucket,'label':label,'count':count,'age':age})
    return result

# ── Artist Connections ─────────────────────────────────
def artist_connections(top_artists, top_tracks):
    """
    Build connection map: artists linked if they appear in same track's artist list
    """
    connections = {}  # artist_id -> {name, images, genres, connected_to: []}
    for a in top_artists:
        connections[a['id']] = {'name':a['name'],'images':a.get('images',[]),'genres':a.get('genres',[]),'connected_to':[]}
    # Connect artists that share a track
    for t in top_tracks:
        artists_in_track = [a['id'] for a in t.get('artists',[])]
        for aid in artists_in_track:
            if aid in connections:
                for other in artists_in_track:
                    if other != aid and other in connections:
                        if other not in connections[aid]['connected_to']:
                            connections[aid]['connected_to'].append(other)
    # Return top 15 most connected artists
    ranked = sorted(connections.values(), key=lambda x: len(x['connected_to']), reverse=True)
    return ranked[:15]

# ── Peak Hours ────────────────────────────────────────
def peak_hours(recent_items):
    """Find exact peak listening hours"""
    hour_count = {}
    for item in recent_items:
        try:
            h = int(item.get('played_at','')[11:13])
            hour_count[h] = hour_count.get(h, 0) + 1
        except: continue
    if not hour_count: return []
    max_h = max(hour_count.values())
    result = []
    for h in range(24):
        c = hour_count.get(h, 0)
        pct = round(c / max_h * 100) if max_h > 0 else 0
        label = f"{h:02d}:00"
        result.append({'hour':h,'label':label,'count':c,'pct':pct})
    # Top 3 hours
    top3 = sorted(hour_count.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_label = f"{top3[0][0]:02d}:00 - {(top3[0][0]+2)%24:02d}:00" if top3 else ""
    return result, peak_label

# ── Other helpers ─────────────────────────────────────
def music_age(top_tracks):
    years = []
    for t in top_tracks:
        yr = t.get('album',{}).get('release_date','0000')[:4]
        if yr.isdigit(): years.append(int(yr))
    if not years: return None
    avg = round(sum(years)/len(years))
    age = datetime.now().year - avg
    decade_pct = {}
    for y in years:
        d = f"{(y//10)*10}s"
        decade_pct[d] = decade_pct.get(d,0) + 1
    dominant = max(decade_pct, key=decade_pct.get)
    return {'avg_year':avg,'age':age,'dominant_decade':dominant}

def discovery_score(top_artists, top_tracks):
    all_pops = [a.get('popularity',0) for a in top_artists] + [t.get('popularity',0) for t in top_tracks]
    if not all_pops: return {'score':50,'label':'未知','avg_pop':0}
    avg_pop = sum(all_pops)/len(all_pops)
    score = max(0, min(100, round((100-avg_pop)*1.2)))
    if score >= 75: label = "🔮 地下音樂獵人"
    elif score >= 50: label = "🌿 獨立品味玩家"
    elif score >= 25: label = "🎬 主流邊緣遊走"
    else: label = "📺 流行天王"
    return {'score':score,'label':label,'avg_pop':round(avg_pop)}

def signal_noise(top_tracks, top_artists):
    ap_map = {a['id']:a.get('popularity',0) for a in top_artists}
    signal, noise = [], []
    for i, t in enumerate(top_tracks[:30]):
        pop = t.get('popularity',0); rank = i+1
        ap = max((ap_map.get(a.get('id',''),0) for a in t.get('artists',[])), default=0)
        avg = (pop+ap)//2
        if avg < 50 and rank <= 15: signal.append((t,avg,rank))
        elif avg > 75 and pop > 70 and rank > 10: noise.append((t,avg,rank))
    signal.sort(key=lambda x: x[2]); noise.sort(key=lambda x: x[1], reverse=True)
    return signal[:5], noise[:5]

def listening_streak(recent_items):
    try:
        days = set(item.get('played_at','')[:10] for item in recent_items if item.get('played_at'))
        if len(days) < 2: return {'days':len(days),'streak':1,'status':'開始建立聆聽習慣'}
        today = datetime.utcnow().date()
        streak, check = 0, today
        for d in reversed(sorted(days)):
            dt = datetime.strptime(d,'%Y-%m-%d').date()
            if dt == check or dt == check - timedelta(days=1): streak += 1; check = dt
            else: break
        if streak >= 7: s = '🎉 音樂狂人'
        elif streak >= 4: s = '💪 穩定聆聽者'
        elif streak >= 2: s = '📈 建立習慣中'
        else: s = '🌱 剛開始探索'
        return {'days':len(days),'streak':streak,'status':s}
    except: return {'days':0,'streak':0,'status':''}

def calendar_heatmap(recent_items):
    heatmap = {}; now = datetime.utcnow()
    for i in range(28):
        day = (now - timedelta(days=i)).strftime('%Y-%m-%d')
        heatmap[day] = 0
    for item in recent_items:
        day = item.get('played_at','')[:10]
        if day in heatmap: heatmap[day] += 1
    max_val = max(heatmap.values()) if heatmap.values() else 1
    result = []
    for day, count in sorted(heatmap.items()):
        dto = datetime.strptime(day,'%Y-%m-%d')
        result.append({'date':day,'day':dto.strftime('%a'),'daynum':dto.day,'count':count,'level':int(count/max_val*4) if max_val>0 else 0})
    return result

# ── Cache ─────────────────────────────────────────────
_CACHE = {}; _TTL = 300
def cache_get(key):
    if key in _CACHE:
        val, ts = _CACHE[key]
        if time.time() - ts < _TTL: return val, True
    return None, False
def cache_set(key, value): _CACHE[key] = (value, time.time())

# ── Tokens ───────────────────────────────────────────
def read_tokens():
    cid = os.environ.get('SPOTIFY_CLIENT_ID')
    cs  = os.environ.get('SPOTIFY_CLIENT_SECRET')
    rt  = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    at  = os.environ.get('SPOTIFY_ACCESS_TOKEN')
    if not cid:
        try:
            with open('/opt/data/.env','rb') as f: raw = f.read()
            cid = re.search(b'SPOTIFY_CLIENT_ID=([a-zA-Z0-9]+)', raw).group(1).decode()
            cs  = re.search(b'SPOTIFY_CLIENT_SECRET=([a-zA-Z0-9]+)', raw).group(1).decode()
            rt  = re.search(b'SPOTIFY_REFRESH_TOKEN=([A-Za-z0-9_-]+)', raw).group(1).decode()
            access = re.search(b'SPOTIFY_ACCESS_TOKEN=([A-Za-z0-9_-]+)', raw)
            at = access.group(1).decode() if access else None
        except: pass
    return {'client_id':cid,'client_secret':cs,'refresh_token':rt,'access_token':at}

def refresh_access_token(cid, cs, rt):
    data = urllib.parse.urlencode({'grant_type':'refresh_token','refresh_token':rt,'client_id':cid,'client_secret':cs}).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=data)
    req.add_header('Content-Type','application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())['access_token']

def get_access_token():
    tokens = read_tokens()
    try:
        req = urllib.request.Request('https://api.spotify.com/v1/me/top/artists?limit=1', headers={'Authorization':f"Bearer {tokens['access_token']}"})
        with urllib.request.urlopen(req, timeout=10) as r: r.read()
        return tokens['access_token']
    except:
        return refresh_access_token(tokens['client_id'], tokens['client_secret'], tokens['refresh_token'])

def api_get(url, cache_key=None):
    if cache_key:
        v, f = cache_get(cache_key)
        if f: return v
    req = urllib.request.Request(url, headers={'Authorization':f"Bearer {get_access_token()}"})
    with urllib.request.urlopen(req, timeout=15) as r: data = json.loads(r.read())
    if cache_key: cache_set(cache_key, data)
    return data

# ── Routes ────────────────────────────────────────────
app.jinja_env.globals['now'] = lambda: datetime.now().strftime('%Y-%m-%d')

@app.route('/')
def index():
    try:
        time_range = request.args.get('range','medium_term')
        top_artists_data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={time_range}', cache_key=f'top_artists_{time_range}')
        top_tracks_data  = api_get(f'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={time_range}', cache_key=f'top_tracks_{time_range}')
        recent_raw       = api_get('https://api.spotify.com/v1/me/player/recently-played?limit=50', cache_key='recent_50')

        top_artists = top_artists_data['items']
        top_tracks  = top_tracks_data['items']
        recent_items = recent_raw['items']

        # Genres
        genre_count = {}
        for a in top_artists:
            for g in a.get('genres',[]): genre_count[g] = genre_count.get(g,0) + 1
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        top_genres = [(g,c) for g,c in sorted_genres if c >= 2]

        features = estimate_features(top_genres)
        dna = taste_dna(top_artists, top_tracks, top_genres)
        decade_data = decade_breakdown(top_tracks)
        artist_conns = artist_connections(top_artists, top_tracks)
        hours_data, peak_label = peak_hours(recent_items)
        signal_t, noise_t = signal_noise(top_tracks, top_artists)
        streak = listening_streak(recent_items)
        heatmap = calendar_heatmap(recent_items)
        music_age_data = music_age(top_tracks)
        discovery = discovery_score(top_artists, top_tracks)

        # Top collaborators
        artist_track_count = {}
        for t in top_tracks:
            for a in t.get('artists',[]):
                aid = a['id']
                if aid not in artist_track_count:
                    artist_track_count[aid] = {'name':a['name'],'images':a.get('images',[]),'count':0}
                artist_track_count[aid]['count'] += 1
        top_collab = sorted(artist_track_count.values(), key=lambda x: x['count'], reverse=True)[:8]

        # Stats
        total_tracks = len(top_tracks)
        explicit_count = sum(1 for t in top_tracks if t.get('explicit'))
        avg_pop = round(sum(t.get('popularity',0) for t in top_tracks)/max(total_tracks,1))
        total_duration_min = round(sum(t.get('duration_ms',0) for t in top_tracks)/60000)

        # Profile
        e,d,v = features['energy'], features['danceability'], features['valence']
        if e > 0.75 and d > 0.7: taste_profile = "⚡ 派對動物"
        elif e > 0.65 and v > 0.6: taste_profile = "🌴 陽光系"
        elif e < 0.45 and d < 0.55: taste_profile = "🌙 沉思者"
        elif d > 0.72: taste_profile = "💃 節奏控"
        elif v < 0.4: taste_profile = "🥀 憂傷美學"
        else: taste_profile = "🎭 多元品味"

        # Share text
        top_artist_name = top_artists[0]['name'] if top_artists else '?'
        top_dna_dim = dna[0]['dim'] if dna else '?'
        share = f"🎵 我的 Spotify 品味分析\nProfile: {taste_profile}\nTop Artist: {top_artist_name}\nMusic Age: {music_age_data['age']}歲\nTaste DNA: {top_dna_dim}導向\nDiscovery: {discovery['label']}\nPeak: {peak_label}\n{streak['status']}"

        return render_template('index.html',
            top_artists=top_artists, top_tracks=top_tracks, recent=recent_items[:20],
            top_genres=top_genres, features=features, time_range=time_range,
            discovery_genres=top_genres[:15], signal_tracks=[s[0] for s in signal_t],
            noise_tracks=[n[0] for n in noise_t], streak=streak, heatmap=heatmap,
            music_age=music_age_data, discovery=discovery, taste_profile=taste_profile,
            share=share, dna=dna, decade_data=decade_data,
            artist_conns=artist_conns[:12], top_collab=top_collab,
            peak_label=peak_label, hours_data=hours_data,
            stats={'explicit':explicit_count,'popularity':avg_pop,'duration':total_duration_min,'genres':len(top_genres)},
        )
    except Exception as e:
        import traceback; return f"<pre>Error: {e}\n\n{traceback.format_exc()}</pre>", 500

@app.route('/api/refresh-token')
def api_refresh():
    try:
        t = read_tokens()
        nt = refresh_access_token(t['client_id'], t['client_secret'], t['refresh_token'])
        return jsonify({'success': True, 'token': nt[:20]+'...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/player', methods=['GET', 'POST', 'PUT'])
def player_control():
    """Control Spotify playback: GET current track, PUT play/pause, POST next/prev"""
    try:
        token = get_access_token()
        method = request.method

        if method == 'GET':
            # Get currently playing
            req = urllib.request.Request(
                'https://api.spotify.com/v1/me/player/currently-playing',
                headers={'Authorization': f'Bearer {token}'}
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    if r.status == 200:
                        data = json.loads(r.read())
                        return jsonify(data)
            except Exception:
                pass
            return jsonify({'is_playing': False}), 200

        elif method == 'PUT':
            # Play or pause
            action = request.args.get('action', 'play')  # play or pause
            req = urllib.request.Request(
                f'https://api.spotify.com/v1/me/player/{action}',
                data=b'',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                method='PUT'
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    return jsonify({'success': True}), r.status or 200
            except urllib.error.HTTPError as e:
                return jsonify({'error': e.read().decode()}), e.code

        elif method == 'POST':
            # Next or previous
            action = request.args.get('action', 'next')  # next or previous
            req = urllib.request.Request(
                f'https://api.spotify.com/v1/me/player/{action}',
                data=b'',
                headers={'Authorization': f'Bearer {token}'},
                method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    return jsonify({'success': True}), r.status or 200
            except urllib.error.HTTPError as e:
                return jsonify({'error': e.read().decode()}), e.code

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/play-track/<track_id>')
def play_track(track_id):
    """Play a specific track on user's active device"""
    try:
        token = get_access_token()
        # First get user's available devices
        req = urllib.request.Request(
            'https://api.spotify.com/v1/me/player/devices',
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            devices = json.loads(r.read())
        active = [d for d in devices.get('devices', []) if d.get('is_active')]
        if not active:
            return jsonify({'error': 'No active device. Open Spotify on your phone/computer first.', 'devices': devices.get('devices', [])}), 400
        device_id = active[0]['id']
        # Play this track
        req2 = urllib.request.Request(
            f'https://api.spotify.com/v1/me/player/play?device_id={device_id}',
            data=json.dumps({'uris': [f'spotify:track:{track_id}']}).encode(),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            method='PUT'
        )
        try:
            with urllib.request.urlopen(req2, timeout=10) as r:
                return jsonify({'success': True, 'track_id': track_id}), 200
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            return jsonify({'error': err}), e.code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
