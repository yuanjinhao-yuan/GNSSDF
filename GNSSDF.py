import subprocess
import json
import sqlite3
import time
import sys
import os
import math
import threading

DB_FILE = "GNSSDF.db"
HEADING_FILE = "heading.txt"
HEADING_MAX_AGE = 3.0

running = True
last_loc = None
count = 0
monitor_heading = False

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL,
            provider TEXT,
            speed REAL,
            heading REAL,
            track_angle REAL,
            track_delta REAL,
            name TEXT,
            time REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_location():
    try:
        result = subprocess.run(
            ['termux-location', '-p', 'gps', '-r', 'once'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

def read_heading():
    if not monitor_heading:
        return None
    try:
        if os.path.exists(HEADING_FILE):
            with open(HEADING_FILE, 'r') as f:
                parts = f.read().strip().split()
                if len(parts) == 2:
                    heading = float(parts[0])
                    ts = float(parts[1])
                    if time.time() - ts <= HEADING_MAX_AGE:
                        return heading
    except Exception:
        pass
    return None
    
def dist_meters(lat1, lon1, lat2, lon2):
    dlat = abs(lat2 - lat1) * 111000
    dlon = abs(lon2 - lon1) * 111000 * math.cos(math.radians(lat1))
    return math.sqrt(dlat ** 2 + dlon ** 2)

def calc_track_angle(lat1, lon1, lat2, lon2):
    """用前后两点的经纬度差，算航迹角（0~360，正北为0）"""
    dx = (lon2 - lon1) * math.cos(math.radians(lat1))
    dy = lat2 - lat1
    angle = math.degrees(math.atan2(dx, dy))
    return (angle + 360) % 360

def normalize_angle_delta(a1, a2):
    """两个角度之间的最小差值（-180~180）"""
    d = (a2 - a1 + 360) % 360
    if d > 180:
        d -= 360
    return d

def save_location(loc, heading, track_angle, track_delta):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'INSERT INTO tracks (latitude, longitude, accuracy, provider, speed, heading, track_angle, track_delta, name, time) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (loc['latitude'], loc['longitude'], loc.get('accuracy', 0),
         loc.get('provider', ''), loc.get('speed', 0),
         heading if heading is not None else 0,
         track_angle if track_angle is not None else 0,
         track_delta if track_delta is not None else 0,
         None,
         time.time())
    )
    conn.commit()
    conn.close()

def input_loop():
    global running, monitor_heading
    while running:
        try:
            cmd = input().strip().lower()
            if cmd == 'exit':
                running = False
                print("\n[*] 收到 exit，正在停止...")
                break
            elif cmd == '1':
                monitor_heading = True
                print("[*] 已开启航向监测（IMU）")
            elif cmd == '2':
                monitor_heading = False
                print("[*] 已关闭航向监测（IMU）")
            else:
                print("[!] 无效输入，请输入 1（开启航向）、2（关闭航向）或 exit（退出）")
        except EOFError:
            break
        except Exception:
            break
            
            
if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("📍 轨迹记录器（GNSSDF）")
    print(f"📁 数据库: {os.path.abspath(DB_FILE)}")
    print(f"🧭 航向来源: {os.path.abspath(HEADING_FILE)}")
    print("🛰  定位方式: GPS")
    print("⏱  采样间隔: 0.5 秒")
    print("⌨️  输入 1 开启航向监测，输入 2 关闭航向监测，输入 exit 停止")
    print("=" * 50)
    print("[!] 请先在另一个终端运行 CL.py\n")

    threading.Thread(target=input_loop, daemon=True).start()

    next_time = time.time()

    try:
        while running:
            now = time.time()
            sleep_time = next_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            next_time += 0.5

            if not running:
                break

            loc = get_location()
            if not loc:
                print("[!] GPS 定位失败，跳过本轮")
                continue

            accuracy = loc.get('accuracy', 999)
            speed = loc.get('speed', 0)

            if accuracy > 60:
                print(f"[!] 精度 {accuracy:.0f}m 太差，跳过")
                continue

            heading = read_heading()

            track_angle = None
            track_delta = None
            if last_loc is not None:
                d = dist_meters(last_loc['latitude'], last_loc['longitude'],
                                loc['latitude'], loc['longitude'])
                if d > 1:
                    track_angle = calc_track_angle(
                        last_loc['latitude'], last_loc['longitude'],
                        loc['latitude'], loc['longitude']
                    )
                    if last_loc.get('track_angle') is not None:
                        track_delta = normalize_angle_delta(last_loc['track_angle'], track_angle)

            moving_speed = speed > 0.5
            moving_distance = False
            if last_loc is not None:
                d = dist_meters(last_loc['latitude'], last_loc['longitude'],
                                loc['latitude'], loc['longitude'])
                moving_distance = d > 2
            else:
                moving_distance = True

            if moving_speed or moving_distance:
                save_location(loc, heading, track_angle, track_delta)
                loc['track_angle'] = track_angle
                last_loc = loc
                count += 1
                h_str = f"{heading:.1f}°" if heading is not None else "N/A"
                t_str = f"{track_angle:.1f}°" if track_angle is not None else "N/A"
                d_str = f"{track_delta:.1f}°" if track_delta is not None else "N/A"
                print(f"[{count}] {loc['latitude']:.6f}, {loc['longitude']:.6f}  "
                      f"精度:{accuracy:.0f}m 速度:{speed:.2f}m/s  "
                      f"航向:{h_str} 航迹角:{t_str} 变化:{d_str}")
            else:
                print(f"[!] 静止，跳过")

    except KeyboardInterrupt:
        running = False
        print(f"\n[*] 手动中断，共记录 {count} 个点")
        sys.exit(0)

    print(f"\n[*] 已停止，共记录 {count} 个点")
    sys.exit(0)