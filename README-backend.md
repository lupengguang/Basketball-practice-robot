# 本地采集后端启动说明

仅作前端展示用途:用本机摄像头代替硬件采集,不加载任何 AI 模型,事件流为模拟数据(参照 OpenHoopVision `basketball_frame_v2` JSONL 格式)。

## 启动

```bash
pip install -r requirements.txt
python server.py
```

访问:

- 实时采集页: http://127.0.0.1:8765/camera.html
- 网站首页:    http://127.0.0.1:8765/

## 接口

| 路径 | 说明 |
| --- | --- |
| `GET /video_feed` | MJPEG 摄像头流,摄像头不可用时输出「摄像头未连接」占位帧 |
| `GET /api/status` | `{camera, fps, resolution, uptime}` |
| `GET /api/events` | 最新 20 条模拟逐帧记录(frame / timestamp / objects / event / possession / score) |
| `GET /<page>.html` | 静态托管网站全部页面 |

## OpenHoopVision 项目

仓库已克隆至 `OpenHoopVision/`(已加入 `.gitignore`,不提交)。其结构要点:`pipeline/` 逐帧协调、`events/` 事件推断(投篮/传球/运球/篮板/抢断/失误)、`render/` 标注渲染,输出为逐帧 JSONL(schema 为 `basketball_frame_v2`,投篮结果标记 `made` / `miss` / `unknown`)。本项目未运行其 AI 流水线,仅借用数据格式生成模拟事件。
