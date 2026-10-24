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

## 数据集接入(nexsports-ball598)

数据集仓库已克隆至 `dataset-nexsports/`(已加入 `.gitignore`,不提交),来源:<https://github.com/VisionMillionDataStudio/nexsports-ball598>。**仅展示数据集自带标注,不运行任何 AI 模型。**

数据集要点:README 描述完整数据集「nexsports-ball」为 10000 张篮球场景图片,YOLO txt 标注,2 个检测类别(`ball` / `player`,非动作分类);仓库实际附带 19 张演示图与训练源码,未包含标签文件,因此接口如实返回 0 条标注并展示类别定义与媒体。启动时后端自动扫描数据集目录构建索引缓存(上限 200 个媒体样本,超出注明截断),支持 YOLO txt 与 COCO json 两种标注解析。

接口清单:

| 路径 | 说明 |
| --- | --- |
| `GET /api/dataset` | 概览 `{name, total_samples, indexed_samples, truncated, format, classes[{id,name,count}], note}` |
| `GET /api/dataset/samples` | 样本列表(最多 50 条:id / file / media_type / classes / annotation_count) |
| `GET /api/dataset/sample/<id>` | 单样本详情:全部标注统一解析为 `{class_id, class, bbox_norm}`(COCO 为 `bbox_xywh_abs`),附 `file_url` 与图片尺寸 |
| `GET /dataset-file/<path>` | 安全返回数据集内媒体文件(经 safe_join 防路径穿越) |

前端入口:`camera.html` 页面底部「数据集标注展示」模块(概览条 + 样本列表 + 标注框叠加预览 + 明细表)。

## OpenHoopVision 项目

仓库已克隆至 `OpenHoopVision/`(已加入 `.gitignore`,不提交)。其结构要点:`pipeline/` 逐帧协调、`events/` 事件推断(投篮/传球/运球/篮板/抢断/失误)、`render/` 标注渲染,输出为逐帧 JSONL(schema 为 `basketball_frame_v2`,投篮结果标记 `made` / `miss` / `unknown`)。本项目未运行其 AI 流水线,仅借用数据格式生成模拟事件。
