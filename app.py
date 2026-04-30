"""
Spotify Taste Analyzer v8 — Flask Backend
Unique: Music Age · Timeless Artists · Energy Arc · Discovery Score · Guilty Pleasures
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

# Cache
_CACHE = {}; _TTL = 300
def cache_get(key):
    if key in _CACHE:
        val, ts = _CACHE[key]
        if time.time() - ts < _TTL: return val, True
    return None, False
def cache_set(key, value): _CACHE[key] = (value, time.time())

# Tokens
def read_tokens():
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    access_token = os.environ.get('SPOTIFY_ACCESS_TOKEN')
    if not client_id:
        try:
            with open('/opt/data/.env','rb') as f:
                raw = f.read()
            client_id = re.search(b'SPOTIFY_CLIENT_ID=([a-zA-Z0-9]+)', raw).group(1).decode()
            client_secret = re.search(b'SPOTIFY_CLIENT_SECRET=([a-zA-Z0-9]+)', raw).group(1).decode()
            refresh_token = re.search(b'SPOTIFY_REFRESH_TOKEN=([A-Za-z0-9_-]+)', raw).group(1).decode()
            access = re.search(b'SPOTIFY_ACCESS_TOKEN=([A-Za-z0-9_-]+)', raw)
            access_token = access.group(1).decode() if access else None
        except: pass
    return {'client_id':client_id,'client_secret':client_secret,'refresh_token':refresh_token,'access_token':access_token}

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

# ── Unique analyses ─────────────────────────────────────

def music_age(top_tracks):
    """Average year + 'music age' in years"""
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
    return {'avg_year': avg, 'age': age, 'dominant_decade': dominant, 'decade_pct': decade_pct}

def timeless_artists(time_range):
    """Find artists that appear across ALL 3 time ranges = truly timeless"""
    ranges = ['short_term','medium_term','long_term']
    artist_ranks = {}  # id -> {name, short, medium, long}
    for r in ranges:
        data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={r}', cache_key=f'top_artists_{r}')
        for i, a in enumerate(data['items']):
            aid = a['id']
            if aid not in artist_ranks:
                artist_ranks[aid] = {'name':a['name'],'images':a.get('images',[]),'genres':a.get('genres',[])}
            artist_ranks[aid][r] = i + 1
    # Keep only artists present in all 3
    timeless = []
    for aid, info in artist_ranks.items():
        if all(r in info for r in ranges):
            avg_rank = sum(info[r] for r in ranges) / 3
            timeless.append({'id':aid,'name':info['name'],'images':info['images'],'genres':info['genres'],'avg_rank':round(avg_rank,1)})
    timeless.sort(key=lambda x: x['avg_rank'])
    return timeless[:8]

def energy_arc(recent_items):
    """Listening energy by time of day"""
    hour_buckets = [
        ('🌅 早晨 6-9',    range(6,9)),
        ('💼 上午 9-12',   range(9,12)),
        ('☀️ 中午 12-14', range(12,14)),
        ('📖 下午 14-18', range(14,18)),
        ('🌆 傍晚 18-21', range(18,21)),
        ('🌙 夜晚 21-24', range(21,24)),
        ('🌃 深夜 0-6',   range(0,6)),
    ]
    counts = {label:0 for label,_ in hour_buckets}
    for item in recent_items:
        try:
            h = int(item.get('played_at','')[11:13])
        except: continue
        for label, r in hour_buckets:
            if h in r: counts[label] += 1; break
    total = sum(counts.values()) or 1
    result = []
    for label, _ in hour_buckets:
        c = counts[label]
        if c > 0:
            result.append({'label':label,'count':c,'pct':round(c/total*100)})
    # Find peak
    if result:
        peak = max(result, key=lambda x: x['count'])
        for r in result:
            r['is_peak'] = (r['label'] == peak['label'])
    return result

def discovery_score(top_artists, top_tracks):
    """How underground is your taste? 0=mainstream, 100=deep cut"""
    artist_pops = [a.get('popularity',0) for a in top_artists]
    track_pops = [t.get('popularity',0) for t in top_tracks]
    all_pops = artist_pops + track_pops
    if not all_pops: return 50
    avg_pop = sum(all_pops) / len(all_pops)
    # 0 pop = underground, 100 = mainstream → invert for discovery
    score = round((100 - avg_pop) * 1.2)  # scale to roughly 0-100
    score = max(0, min(100, score))
    # Labels
    if score >= 75: label = "🔮 地下音樂獵人"
    elif score >= 50: label = "🌿 獨立品味玩家"
    elif score >= 25: label = "🎬 主流邊緣遊走"
    else: label = "📺 流行趨勢達人"
    return {'score': score, 'label': label, 'avg_pop': round(avg_pop)}

def guiltyPleasures(top_tracks):
    """High dance + low energy = guilty pleasure territory"""
    gp = []
    for t in top_tracks[:30]:
        pop = t.get('popularity', 0)
        # Fake danceability from genres
        dance = 0.5
        genres = t.get('album',{}).get('artists',[{}])[0].get('genres',[])
        for g in genres:
            gl = g.lower()
            if 'pop' in gl: dance = 0.75
            if 'k-pop' in gl or 'j-pop' in gl: dance = 0.82
            if 'dance' in gl: dance = 0.85
        # High popularity + high danceability + not super high energy
        if pop > 60 and dance > 0.65:
            gp.append({'track':t,'dance':dance,'pop':pop})
    gp.sort(key=lambda x: x['dance'], reverse=True)
    return gp[:5]

def signal_noise(top_tracks, top_artists):
    artist_pop_map = {a['id']:a.get('popularity',0) for a in top_artists}
    signal, noise = [], []
    for i, t in enumerate(top_tracks[:30]):
        pop = t.get('popularity',0)
        rank = i + 1
        ap = max((artist_pop_map.get(a.get('id',''),0) for a in t.get('artists',[])), default=0)
        avg = (pop + ap) // 2
        if avg < 50 and rank <= 15: signal.append((t, avg, rank))
        elif avg > 75 and pop > 70 and rank > 10: noise.append((t, avg, rank))
    signal.sort(key=lambda x: x[2])
    noise.sort(key=lambda x: x[1], reverse=True)
    return signal[:5], noise[:5]

def listening_streak(recent_items):
    try:
        days = set(item.get('played_at','')[:10] for item in recent_items if item.get('played_at'))
        day_list = sorted(days)
        if len(day_list) < 2: return {'days':len(days),'streak':1,'status':'開始建立聆聽習慣'}
        today = datetime.utcnow().date()
        streak, check = 0, today
        for d in reversed(day_list):
            dt = datetime.strptime(d,'%Y-%m-%d').date()
            if dt == check or dt == check - timedelta(days=1):
                streak += 1; check = dt
            else: break
        if streak >= 7: s = '🎉 音樂狂人！連續聆聽習慣超強'
        elif streak >= 4: s = '💪 穩定聆聽者'
        elif streak >= 2: s = '📈 正在建立習慣'
        else: s = '🌱 剛開始探索'
        return {'days':len(days),'streak':streak,'status':s}
    except: return {'days':0,'streak':0,'status':''}

def calendar_heatmap(recent_items):
    heatmap = {}
    now = datetime.utcnow()
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

# ── Routes ───────────────────────────────────────────────────────

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

        # Features
        features = estimate_features(top_genres)

        # Unique analyses
        music_age_data = music_age(top_tracks)
        timeless = timeless_artists(time_range)
        energy_arc_data = energy_arc(recent_items)
        discovery = discovery_score(top_artists, top_tracks)
        gp = guiltyPleasures(top_tracks)
        signal_t, noise_t = signal_noise(top_tracks, top_artists)
        streak = listening_streak(recent_items)
        heatmap = calendar_heatmap(recent_items)

        # Stats
        total_tracks = len(top_tracks)
        explicit_count = sum(1 for t in top_tracks if t.get('explicit'))
        avg_pop = round(sum(t.get('popularity',0) for t in top_tracks)/max(total_tracks,1))
        total_duration_min = round(sum(t.get('duration_ms',0) for t in top_tracks)/60000)

        # Taste profile
        e,d,v = features['energy'], features['danceability'], features['valence']
        if e > 0.75 and d > 0.7: taste_profile = "⚡ 派對動物"
        elif e > 0.65 and v > 0.6: taste_profile = "🌴 陽光系"
        elif e < 0.45 and d < 0.55: taste_profile = "🌙 沉思者"
        elif d > 0.72: taste_profile = "💃 節奏控"
        elif v < 0.4: taste_profile = "🥀 憂傷美學"
        else: taste_profile = "🎭 多元品味"

        # Share text
        top_artist_name = top_artists[0]['name'] if top_artists else '?'
        share = f"🎵 我的 Spotify 品味分析\nProfile: {taste_profile}\nTop Artist: {top_artist_name}\nMusic Age: {music_age_data['age']}歲 | {discovery['label']}\nAvg BPM: {features['tempo']} | Dance: {int(features['danceability']*100)}% | Energy: {int(features['energy']*100)}%\n{streak['status']}"

        return render_template('index.html',
            top_artists=top_artists, top_tracks=top_tracks, recent=recent_items[:20],
            top_genres=top_genres, features=features, time_range=time_range,
            discovery_genres=top_genres[:12], signal_tracks=[s[0] for s in signal_t],
            noise_tracks=[n[0] for n in noise_t], streak=streak, heatmap=heatmap,
            music_age=music_age_data, timeless=timeless, energy_arc=energy_arc_data,
            discovery=discovery, guilty_pleasures=gp, taste_profile=taste_profile, share=share,
            stats={'explicit':explicit_count,'popularity':avg_pop,'duration':total_duration_min,'genres':len(top_genres)},
        )
    except Exception as e:
        import traceback; return f"<pre>Error: {e}\n\n{traceback.format_exc()}</pre>", 500

@app.route('/api/compare-ranges')
def api_compare_ranges():
    try:
        ranges = {'short_term':'4週','medium_term':'6個月','long_term':'All Time'}
        all_genres = {}
        all_artists = {}
        for r in ranges:
            data = api_get(f'https://api.spotify.com/v1/me/top/artists?limit=50&time_range={r}', cache_key=f'top_artists_{r}')
            for i, a in enumerate(data['items']):
                aid = a['id']
                if aid not in all_artists: all_artists[aid] = {'name':a['name'],'images':a.get('images',[])}
                all_artists[aid][f'{r}_rank'] = i+1
                for g in a.get('genres',[]):
                    if g not in all_genres: all_genres[g] = {'short':0,'medium':0,'long':0}
                    all_genres[g][r] = all_genres[g].get(r,0)+1
        rising, declining = [], []
        for g, c in all_genres.items():
            s,m,l = c.get('short',0),c.get('medium',0),c.get('long',0)
            if s+m+l < 3: continue
            if s > m > l: rising.append({'genre':g,'short':s,'medium':m,'long':l})
            elif l > m > s: declining.append({'genre':g,'short':s,'medium':m,'long':l})
        rising.sort(key=lambda x: x['short'], reverse=True)
        declining.sort(key=lambda x: x['long'], reverse=True)
        return jsonify({'rising':rising[:5],'declining':declining[:5]})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/api/refresh-token')
def api_refresh():
    try:
        t = read_tokens()
        nt = refresh_access_token(t['client_id'], t['client_secret'], t['refresh_token'])
        return jsonify({'success':True,'token':nt[:20]+'...'})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
