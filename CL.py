import subprocess
import json
import time
import os
import sys

HEADING_FILE = 'heading.txt'
INTERVAL = 1

# 匹配优先级：Orientation > Rotation Vector > 任意含 "Orientation" 的
SENSOR_KEYWORDS = ['Orientation', 'Rotation Vector', 'Rotation']


def list_sensors():
    """列出设备上所有可用的传感器"""
    try:
        result = subprocess.run(
            ['termux-sensor', '-l'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        # termux-sensor -l 的输出结构通常是 {"sensors": ["...", "..."]}
        return data.get('sensors', [])
    except Exception:
        return []


def find_orientation_sensor():
    """在传感器列表里找一个能提供航向的传感器"""
    sensors = list_sensors()
    if not sensors:
        return None

    # 按关键词优先级匹配
    for keyword in SENSOR_KEYWORDS:
        for s in sensors:
            if keyword.lower() in s.lower():
                return s
    return None


def read_sensor(name, n=3):
    try:
        result = subprocess.run(
            ['termux-sensor', '-s', name, '-n', str(n)],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(result.stdout.strip())
            sensor_data = data.get(name, {})
            values = sensor_data.get('values', [])

            if values and isinstance(values[0], (int, float)):
                return values
            elif values and isinstance(values[0], list):
                return values[-1]
            return []
    except Exception:
        pass
    return []


def main():
    print("[*] 正在扫描可用传感器...")
    sensor_name = find_orientation_sensor()

    if not sensor_name:
        print("[!] 未找到可用的航向传感器。")
        print("[!] 请手动运行 termux-sensor -l 查看传感器列表，")
        print("[!] 并把想要的传感器名字填到 SENSOR_KEYWORDS 里。")
        sys.exit(1)

    print(f"[*] 已选择传感器: {sensor_name}")
    print(f"[*] CL.py 常驻启动，每 {INTERVAL} 秒更新一次航向")
    print(f"[*] 写入: {os.path.abspath(HEADING_FILE)}")
    print("[*] Ctrl+C 停止\n")

    while True:
        v = read_sensor(sensor_name, 3)
        if v and len(v) >= 1:
            heading = v[0]
            heading = (heading + 360) % 360

            with open(HEADING_FILE, 'w') as f:
                f.write(f"{heading:.2f} {time.time():.3f}")

            print(f"[CL] 航向: {heading:.1f}°")
        time.sleep(INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] CL.py 停止")
