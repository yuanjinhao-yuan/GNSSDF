# GNSSDF

一个基于 GNSS + IMU 的轨迹记录与可视化系统，跑在 Termux 上。

## 功能

- 高频采样（0.5 秒/点）
- 航迹角推算
- 航向融合（可选开启 IMU）
- SQLite 本地存储
- 实时 Web 可视化（SSE）
- 时间滑块回放
- JSON 导出

## 文件

- `GNSSDF.py`：轨迹采集主程序
- `GNSSDF2.py`：Flask + SSE 实时可视化
- `CL.py`：IMU 航向采集（可选）

## 运行

```bash
python GNSSDF.py
python GNSSDF2.py