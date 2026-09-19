import sqlite3
from flask import Flask, jsonify, Response, request
import json
import time

app = Flask(__name__)
DB_FILE = "GNSSDF.db"

HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>轨迹实时视图</title>
<style>
  body { margin: 0; padding: 0; background: #1e1e2f; color: #fff; font-family: monospace; overflow: hidden; }
  #info { padding: 8px 12px; background: #2a2a3f; font-size: 13px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
  #info span { color: #22c55e; }
  #canvas-wrap { position: relative; width: 100vw; height: calc(100vh - 40px); }
  canvas { display: block; width: 100%; height: 100%; background: #111; touch-action: none; }
  #controls {
    position: absolute; top: 10px; right: 10px;
    display: flex; flex-direction: column; gap: 6px;
    background: rgba(0,0,0,0.7); padding: 8px; border-radius: 6px;
  }
  #controls button, #controls input {
    font-size: 12px; padding: 5px 8px; border-radius: 4px; border: 1px solid #444;
    background: #2a2a3f; color: #fff; font-family: monospace;
  }
  #controls button.active { background: #22c55e; color: #000; }
  #jump-box { display: flex; gap: 4px; }
  #jump-box input { width: 60px; }
  #hint { position: absolute; bottom: 10px; left: 10px; color: #888; font-size: 12px; background: rgba(0,0,0,0.6); padding: 6px 10px; border-radius: 4px; }
</style>
</head>
<body>
<div id="info">
  <div>点数: <span id="count">0</span></div>
  <div>最新: <span id="latest">-</span></div>
  <div>航迹角: <span id="track">-</span></div>
  <div>拐点: <span id="turn">0</span></div>
</div>
<div id="canvas-wrap">
  <canvas id="canvas"></canvas>
  <div id="controls">
    <button id="btnFollow">自动跟随: 关</button>
    <div id="jump-box">
      <input id="jumpInput" type="number" placeholder="序号" min="1">
      <button id="btnJump">跳转</button>
    </div>
  </div>
  <div id="hint">滚轮缩放 · 拖动平移 · 双击复位 · 点击点命名</div>
</div>

<script>
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let allPoints = [];
let viewScale = 1;
let viewOffsetX = 0;
let viewOffsetY = 0;
let baseScale = 1;
let baseOffsetX = 0;
let baseOffsetY = 0;
let isDragging = false;
let lastX = 0, lastY = 0;
let follow = false;
let latestPoint = null;

function resizeCanvas() {
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = rect.height + 'px';
  ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
  render();
}

function computeBase() {
  if (allPoints.length === 0) return;
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const p of allPoints) {
    if (p.latitude < minLat) minLat = p.latitude;
    if (p.latitude > maxLat) maxLat = p.latitude;
    if (p.longitude < minLon) minLon = p.longitude;
    if (p.longitude > maxLon) maxLon = p.longitude;
  }
  const W = canvas.width / window.devicePixelRatio;
  const H = canvas.height / window.devicePixelRatio;
  const margin = 40;
  const latRange = (maxLat - minLat) || 0.0001;
  const lonRange = (maxLon - minLon) || 0.0001;
  const scaleX = (W - margin * 2) / lonRange;
  const scaleY = (H - margin * 2) / latRange;
  baseScale = Math.min(scaleX, scaleY);
  baseOffsetX = margin + (W - margin * 2 - lonRange * baseScale) / 2;
  baseOffsetY = margin + (H - margin * 2 - latRange * baseScale) / 2;
  window._minLat = minLat; window._maxLat = maxLat;
  window._minLon = minLon; window._maxLon = maxLon;
}

function toXY(lat, lon) {
  const W = canvas.width / window.devicePixelRatio;
  const H = canvas.height / window.devicePixelRatio;
  let x = baseOffsetX + (lon - window._minLon) * baseScale;
  let y = baseOffsetY + (window._maxLat - lat) * baseScale;
  const cx = W / 2, cy = H / 2;
  x = (x - cx) * viewScale + cx + viewOffsetX;
  y = (y - cy) * viewScale + cy + viewOffsetY;
  return [x, y];
}

function render() {
  const W = canvas.width / window.devicePixelRatio;
  const H = canvas.height / window.devicePixelRatio;
  ctx.clearRect(0, 0, W, H);

  document.getElementById('count').textContent = allPoints.length;

  if (allPoints.length === 0) {
    ctx.fillStyle = '#888';
    ctx.font = '16px monospace';
    ctx.fillText('暂无轨迹数据', 20, 40);
    return;
  }

  if (follow && latestPoint) {
    const [lx, ly] = toXY(latestPoint.latitude, latestPoint.longitude);
    const cx = W / 2, cy = H / 2;
    viewOffsetX += cx - lx;
    viewOffsetY += cy - ly;
  }

  // 用二次贝塞尔曲线连接相邻点，让拐弯更平滑
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < allPoints.length; i++) {
    const [x, y] = toXY(allPoints[i].latitude, allPoints[i].longitude);
    if (i === 0) {
      ctx.moveTo(x, y);
    } else if (i === 1) {
      ctx.lineTo(x, y);
    } else {
      const [px, py] = toXY(allPoints[i - 1].latitude, allPoints[i - 1].longitude);
      const [ppx, ppy] = toXY(allPoints[i - 2].latitude, allPoints[i - 2].longitude);
      const mx = (px + x) / 2;
      const my = (py + y) / 2;
      ctx.quadraticCurveTo(px, py, mx, my);
    }
  }
  ctx.stroke();

  // 绘制点位和拐点
  let turnCount = 0;
  for (let i = 0; i < allPoints.length; i++) {
    const p = allPoints[i];
    const [x, y] = toXY(p.latitude, p.longitude);
    const delta = Math.abs(p.track_delta || 0);
    if (delta > 30) {
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
      turnCount++;
    } else {
      ctx.fillStyle = p.name ? '#f59e0b' : '#3b82f6';
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
    if (p.name) {
      ctx.fillStyle = '#f59e0b';
      ctx.font = '11px monospace';
      ctx.fillText(p.name, x + 5, y - 5);
    }
  }
  document.getElementById('turn').textContent = turnCount;

  const [sx, sy] = toXY(allPoints[0].latitude, allPoints[0].longitude);
  ctx.fillStyle = '#22c55e';
  ctx.beginPath();
  ctx.arc(sx, sy, 5, 0, Math.PI * 2);
  ctx.fill();
  
if (latestPoint) {
    const [ex, ey] = toXY(latestPoint.latitude, latestPoint.longitude);
    ctx.fillStyle = '#f59e0b';
    ctx.beginPath();
    ctx.arc(ex, ey, 6, 0, Math.PI * 2);
    ctx.fill();
  }
}

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  const newScale = viewScale * factor;
  if (newScale < 0.1 || newScale > 100) return;
  viewScale = newScale;
  render();
}, { passive: false });

let lastTouchDist = 0;
canvas.addEventListener('touchstart', (e) => {
  if (e.touches.length === 2) {
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    lastTouchDist = Math.sqrt(dx * dx + dy * dy);
  } else if (e.touches.length === 1) {
    isDragging = true;
    lastX = e.touches[0].clientX;
    lastY = e.touches[0].clientY;
  }
}, { passive: false });

canvas.addEventListener('touchmove', (e) => {
  e.preventDefault();
  if (e.touches.length === 2) {
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (lastTouchDist > 0) {
      const factor = dist / lastTouchDist;
      const newScale = viewScale * factor;
      if (newScale >= 0.1 && newScale <= 100) {
        viewScale = newScale;
        render();
      }
    }
    lastTouchDist = dist;
  } else if (e.touches.length === 1 && isDragging) {
    const x = e.touches[0].clientX;
    const y = e.touches[0].clientY;
    viewOffsetX += x - lastX;
    viewOffsetY += y - lastY;
    lastX = x;
    lastY = y;
    render();
  }
}, { passive: false });

canvas.addEventListener('touchend', () => {
  isDragging = false;
  lastTouchDist = 0;
});

canvas.addEventListener('mousedown', (e) => {
  isDragging = true;
  lastX = e.clientX;
  lastY = e.clientY;
});
canvas.addEventListener('mousemove', (e) => {
  if (!isDragging) return;
  viewOffsetX += e.clientX - lastX;
  viewOffsetY += e.clientY - lastY;
  lastX = e.clientX;
  lastY = e.clientY;
  render();
});
canvas.addEventListener('mouseup', () => { isDragging = false; });
canvas.addEventListener('mouseleave', () => { isDragging = false; });

canvas.addEventListener('dblclick', () => {
  viewScale = 1;
  viewOffsetX = 0;
  viewOffsetY = 0;
  render();
});

canvas.addEventListener('click', (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  for (let i = 0; i < allPoints.length; i++) {
    const [x, y] = toXY(allPoints[i].latitude, allPoints[i].longitude);
    const d = Math.sqrt((x - mx) ** 2 + (y - my) ** 2);
    if (d < 10) {
      const name = prompt('给这个点命名（留空取消）:', allPoints[i].name || '');
      if (name !== null) {
        fetch('/api/rename', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: allPoints[i].id, name: name })
        }).then(() => {
          allPoints[i].name = name;
          render();
        });
      }
      break;
    }
  }
});

document.getElementById('btnFollow').addEventListener('click', () => {
  follow = !follow;
  const btn = document.getElementById('btnFollow');
  btn.textContent = follow ? '自动跟随: 开' : '自动跟随: 关';
  btn.classList.toggle('active', follow);
  if (follow) render();
});

document.getElementById('btnJump').addEventListener('click', () => {
  const idx = parseInt(document.getElementById('jumpInput').value);
  if (isNaN(idx) || idx < 1 || idx > allPoints.length) {
    alert('序号超出范围');
    return;
  }
  const p = allPoints[idx - 1];
  latestPoint = p;
  follow = false;
  document.getElementById('btnFollow').textContent = '自动跟随: 关';
  document.getElementById('btnFollow').classList.remove('active');
  viewScale = 3;
  viewOffsetX = 0;
  viewOffsetY = 0;
  computeBase();
  render();
});

function startStream() {
  const es = new EventSource('/api/stream');
  es.onmessage = (e) => {
    const p = JSON.parse(e.data);
    allPoints.push(p);
    latestPoint = p;
    document.getElementById('latest').textContent =
      `${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}`;
    document.getElementById('track').textContent =
      p.track_angle ? p.track_angle.toFixed(1) + '°' : '-';
    if (!window._minLat) computeBase();
    render();
  };
  es.onerror = () => {
    console.log('SSE 断开，3 秒后重连');
    es.close();
    setTimeout(startStream, 3000);
  };
}

async function init() {
  const res = await fetch('/api/tracks');
  allPoints = await res.json();
  if (allPoints.length > 0) latestPoint = allPoints[allPoints.length - 1];
  computeBase();
  render();
  startStream();
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();
init();
</script>
</body>
</html>'''

@app.route('/')
def index():
    return HTML

@app.route('/api/tracks')
def tracks():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, latitude, longitude, accuracy, speed, heading, track_angle, track_delta, name, time '
              'FROM tracks ORDER BY time ASC')
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'id': r[0], 'latitude': r[1], 'longitude': r[2], 'accuracy': r[3],
        'speed': r[4], 'heading': r[5], 'track_angle': r[6],
        'track_delta': r[7], 'name': r[8], 'time': r[9]
    } for r in rows])

@app.route('/api/stream')
def stream():
    def event_stream():
        last_id = 0
        while True:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT id, latitude, longitude, accuracy, speed, heading, track_angle, track_delta, name, time '
                      'FROM tracks WHERE id > ? ORDER BY id ASC', (last_id,))
            rows = c.fetchall()
            conn.close()

            for r in rows:
                last_id = r[0]
                yield f"data: {json.dumps({
                    'id': r[0], 'latitude': r[1], 'longitude': r[2], 'accuracy': r[3],
                    'speed': r[4], 'heading': r[5], 'track_angle': r[6],
                    'track_delta': r[7], 'name': r[8], 'time': r[9]
                })}\n\n"

            time.sleep(1)

    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/api/rename', methods=['POST'])
def rename_point():
    data = request.get_json()
    point_id = data.get('id')
    name = data.get('name', '')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE tracks SET name = ? WHERE id = ?', (name, point_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    print("=" * 50)
    print("🗺️  轨迹实时视图已启动")
    print("📡 监听端口: 8000")
    print(f"📁 数据库: {DB_FILE}")
    print("🌐 浏览器访问: http://127.0.0.1:8000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8000, debug=False)