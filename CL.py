import subprocess
import json
import time
import os

ORIENTATION_SENSOR = 'LSM6DB0 iNemoEngine Orientation Sensor'
HEADING_FILE = 'heading.txt'
INTERVAL = 1


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
    print(f"[*] CL.py 常驻启动，每 {INTERVAL} 秒更新一次航向")
    print(f"[*] 写入: {os.path.abspath(HEADING_FILE)}")
    print("[*] Ctrl+C 停止\n")

    while True:
        v = read_sensor(ORIENTATION_SENSOR, 3)
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
        
        
        