# -*- coding: utf-8 -*-
"""篮训BOT 本地摄像头采集后端(演示用途,不加载任何 AI 模型)。

- GET /video_feed   MJPEG 摄像头流,摄像头不可用时输出占位帧
- GET /api/status   摄像头状态 / FPS / 分辨率 / 运行时长
- GET /api/events   模拟逐帧事件流(参照 OpenHoopVision basketball_frame_v2 JSONL 格式)
- GET /api/dataset* nexsports-ball598 数据集自带标注的只读展示(不跑任何模型)
- GET / 与 /<page>.html  静态托管网站页面
"""
import itertools
import json
import os
import random
import re
import threading
import time
from collections import deque

import cv2
import numpy as np
from flask import Flask, Response, abort, jsonify, send_from_directory

HOST = "127.0.0.1"
PORT = 8765
START_TIME = time.time()

app = Flask(__name__, static_folder=".", static_url_path="")

# ---------------- 摄像头 ----------------
_cap = None
_cap_lock = threading.Lock()


def get_capture():
    global _cap
    with _cap_lock:
        if _cap is None or not _cap.isOpened():
            _cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not _cap.isOpened():
                _cap = cv2.VideoCapture(0)
        return _cap if _cap.isOpened() else None


def camera_info():
    cap = get_capture()
    if cap is None:
        return False, 0.0, (0, 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    return True, round(fps if fps > 1 else 30.0, 1), (w, h)


def placeholder_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (28, 25, 22)
    cv2.rectangle(frame, (20, 20), (620, 460), (60, 60, 68), 2)
    cv2.putText(frame, "CAMERA OFFLINE", (170, 220), cv2.FONT_HERSHEY_SIMPLEX,
                1.2, (90, 90, 100), 2, cv2.LINE_AA)
    cv2.putText(frame, "please check device connection", (150, 270),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (70, 70, 80), 1, cv2.LINE_AA)
    return frame


def mjpeg_generator():
    while True:
        cap = get_capture()
        frame = None
        if cap is not None:
            ok, frame = cap.read()
            if not ok:
                frame = None
        if frame is None:
            frame = placeholder_frame()
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            time.sleep(0.05)
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + jpg.tobytes() + b"\r\n")
        time.sleep(1 / 30.0)


# ---------------- 模拟事件流(basketball_frame_v2 风格) ----------------
EVENT_BUFFER = deque(maxlen=60)
_frame_counter = itertools.count(1)
_score = {"red": 58, "blue": 54}
_possession = "red"

PLAYERS = [
    {"id": "P1", "team": "red"}, {"id": "P2", "team": "red"}, {"id": "P3", "team": "red"},
    {"id": "P4", "team": "blue"}, {"id": "P5", "team": "blue"}, {"id": "P6", "team": "blue"},
]
# 随机游走位置
_pos = {p["id"]: [random.uniform(60, 580), random.uniform(60, 300)] for p in PLAYERS}
_pos["ball"] = [320.0, 180.0]

EVENT_TYPES = ["shot", "pass", "dribble", "rebound", "steal", "turnover"]
EVENT_WEIGHTS = [0.22, 0.30, 0.24, 0.08, 0.08, 0.08]


def _walk(key, speed=42):
    x, y = _pos[key]
    x = min(600, max(40, x + random.uniform(-speed, speed)))
    y = min(320, max(40, y + random.uniform(-speed, speed)))
    _pos[key] = [x, y]
    return x, y


def _make_event(frame_no):
    global _possession
    etype = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS)[0]
    player = random.choice(PLAYERS)
    event = {"type": etype, "player_id": player["id"], "team": player["team"],
             "confidence": round(random.uniform(0.82, 0.99), 2)}
    if etype == "shot":
        result = random.choices(["made", "miss", "unknown"], weights=[0.45, 0.4, 0.15])[0]
        points = random.choice([2, 2, 2, 3])
        event["result"] = result
        event["shot_value"] = points
        if result == "made":
            _score[player["team"]] += points
            event["points"] = points
            _possession = "blue" if player["team"] == "red" else "red"
    elif etype == "pass":
        teammates = [p for p in PLAYERS if p["team"] == player["team"] and p["id"] != player["id"]]
        event["receiver_id"] = random.choice(teammates)["id"]
    elif etype == "rebound":
        event["rebound_type"] = random.choice(["offensive", "defensive"])
    elif etype in ("steal", "turnover"):
        _possession = "blue" if player["team"] == "red" else "red"
    return event


def generate_frame_record():
    frame_no = next(_frame_counter)
    objects = []
    for p in PLAYERS:
        x, y = _walk(p["id"])
        objects.append({
            "id": p["id"], "class": "player", "team": p["team"],
            "bbox": [round(x - 14, 1), round(y - 34, 1), 28, 68],
            "confidence": round(random.uniform(0.85, 0.99), 2),
        })
    bx, by = _walk("ball", 90)
    objects.append({"id": "ball", "class": "ball", "team": None,
                    "bbox": [round(bx - 5, 1), round(by - 5, 1), 10, 10],
                    "confidence": round(random.uniform(0.75, 0.98), 2)})
    objects.append({"id": "rim_left", "class": "rim", "team": None,
                    "bbox": [48, 172, 14, 8], "confidence": 0.99})
    event = _make_event(frame_no) if random.random() < 0.65 else None
    record = {
        "schema": "basketball_frame_v2",
        "frame": frame_no,
        "timestamp": round(time.time() - START_TIME, 3),
        "objects": objects,
        "event": event,
        "possession": _possession,
        "score": dict(_score),
    }
    EVENT_BUFFER.append(record)
    return record


def _event_simulator():
    while True:
        generate_frame_record()
        time.sleep(1.2)


threading.Thread(target=_event_simulator, daemon=True).start()
for _ in range(12):  # 预填缓冲,前端首次加载即有数据
    generate_frame_record()

# ---------------- 数据集(nexsports-ball598,仅展示自带标注,不跑模型) ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset-nexsports")
DATASET_NAME = "nexsports-ball598"
DATASET_MAX_INDEX = 200  # 数据集体积大时仅索引前 200 个媒体样本
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

_DS = {"ready": False, "samples": [], "classes": [], "format": "unknown",
       "total_media": 0, "indexed": 0, "truncated": False, "note": ""}


def _find_class_names():
    """依次从 data.yaml / classes.txt / README 中解析类别名列表。"""
    for root, _dirs, files in os.walk(DATASET_DIR):
        for fn in files:
            low = fn.lower()
            path = os.path.join(root, fn)
            if low in ("classes.txt",):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    names = [ln.strip() for ln in f if ln.strip()]
                if names:
                    return names
            if low.endswith((".yaml", ".yml")):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    m = re.search(r"names\s*:\s*\[([^\]]+)\]", f.read())
                if m:
                    return [s.strip().strip("'\"") for s in m.group(1).split(",")]
    readme = os.path.join(DATASET_DIR, "README.md")
    if os.path.isfile(readme):
        with open(readme, encoding="utf-8", errors="ignore") as f:
            m = re.search(r"names\s*:\s*\[([^\]]+)\]", f.read())
        if m:
            return [s.strip().strip("'\"") for s in m.group(1).split(",")]
    return []


def _parse_yolo_label(path, names):
    """解析 YOLO txt:class_id x_center y_center w h(归一化)。"""
    anns = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            parts = ln.split()
            if len(parts) < 5:
                continue
            try:
                cid = int(float(parts[0]))
                xc, yc, w, h = (float(v) for v in parts[1:5])
            except ValueError:
                continue
            anns.append({
                "class_id": cid,
                "class": names[cid] if 0 <= cid < len(names) else f"class_{cid}",
                "bbox_norm": [round(xc, 6), round(yc, 6), round(w, 6), round(h, 6)],
            })
    return anns


def _yolo_label_for(media_path):
    """按 YOLO 约定查找同名标签:同目录或 images/ -> labels/ 镜像目录。"""
    stem = os.path.splitext(media_path)[0] + ".txt"
    if os.path.isfile(stem):
        return stem
    parts = os.path.normpath(media_path).split(os.sep)
    if "images" in [p.lower() for p in parts]:
        idx = [i for i, p in enumerate(parts) if p.lower() == "images"][0]
        cand = os.path.join(os.sep.join(parts[:idx]), "labels", *parts[idx + 1:])
        cand = os.path.splitext(cand)[0] + ".txt"
        if os.path.isfile(cand):
            return cand
    return None


def _build_dataset_index():
    names = _find_class_names()
    media = []
    coco_json = None
    for root, _dirs, files in os.walk(DATASET_DIR):
        for fn in sorted(files):
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            full = os.path.join(root, fn)
            if ext in IMAGE_EXTS | VIDEO_EXTS:
                media.append(full)
            elif ext == ".json" and coco_json is None:
                try:
                    with open(full, encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "annotations" in data and "images" in data:
                        coco_json = (full, data)
                except (ValueError, OSError):
                    pass
    _DS["total_media"] = len(media)
    _DS["truncated"] = len(media) > DATASET_MAX_INDEX
    media = media[:DATASET_MAX_INDEX]
    _DS["indexed"] = len(media)

    samples = []
    class_counts = {n: 0 for n in names}
    if coco_json:  # COCO 模式
        _DS["format"] = "COCO json"
        path, data = coco_json
        cats = {c["id"]: c["name"] for c in data.get("categories", [])}
        if not names:
            names = [c["name"] for c in sorted(data.get("categories", []),
                                               key=lambda c: c["id"])]
            class_counts = {n: 0 for n in names}
        img_info = {im["id"]: im for im in data.get("images", [])}
        by_img = {}
        for ann in data.get("annotations", []):
            by_img.setdefault(ann.get("image_id"), []).append(ann)
        _DS["note"] = f"标注文件:{os.path.basename(path)}"
        for i, mp in enumerate(media):
            rel = os.path.relpath(mp, DATASET_DIR).replace(os.sep, "/")
            base = os.path.basename(mp)
            hit = next((iid for iid, im in img_info.items()
                        if os.path.basename(im.get("file_name", "")) == base), None)
            anns = []
            if hit is not None:
                for a in by_img.get(hit, []):
                    cname = cats.get(a.get("category_id"), f"class_{a.get('category_id')}")
                    anns.append({"class_id": a.get("category_id"), "class": cname,
                                 "bbox_xywh_abs": [round(v, 2) for v in a.get("bbox", [])]})
                    if cname in class_counts:
                        class_counts[cname] += 1
            samples.append({"id": i, "file": rel, "media_type": "image", "annotations": anns})
    else:  # YOLO 模式(无标签文件时标注为空)
        _DS["format"] = "YOLO txt"
        for i, mp in enumerate(media):
            rel = os.path.relpath(mp, DATASET_DIR).replace(os.sep, "/")
            ext = os.path.splitext(mp)[1].lower()
            mtype = "video" if ext in VIDEO_EXTS else "image"
            anns = []
            label = _yolo_label_for(mp) if mtype == "image" else None
            if label:
                anns = _parse_yolo_label(label, names)
                for a in anns:
                    if a["class"] in class_counts:
                        class_counts[a["class"]] += 1
            samples.append({"id": i, "file": rel, "media_type": mtype, "annotations": anns})
        if not any(s["annotations"] for s in samples):
            _DS["note"] = ("该仓库仅附带演示图片与训练源码,未包含实际标注文件"
                           "(README 描述完整数据集为 10000 张图、YOLO 格式);"
                           "以下展示其自带媒体与类别定义")

    # 读取图片尺寸(用于前端像素换算;imdecode 兼容中文路径)
    for s in samples:
        if s["media_type"] == "image":
            try:
                buf = np.fromfile(os.path.join(DATASET_DIR, s["file"]), dtype=np.uint8)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is not None:
                    s["width"], s["height"] = int(img.shape[1]), int(img.shape[0])
            except OSError:
                pass
    _DS["classes"] = [{"id": i, "name": n, "count": class_counts.get(n, 0)}
                      for i, n in enumerate(names)]
    _DS["samples"] = samples
    _DS["ready"] = True


if os.path.isdir(DATASET_DIR):
    _build_dataset_index()
else:
    _DS["note"] = "数据集目录 dataset-nexsports 不存在,请先克隆数据集仓库"


# ---------------- 路由 ----------------


@app.route("/video_feed")
def video_feed():
    return Response(mjpeg_generator(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def api_status():
    ok, fps, (w, h) = camera_info()
    return jsonify({
        "camera": ok,
        "fps": fps,
        "resolution": f"{w}x{h}" if ok else "-",
        "uptime": round(time.time() - START_TIME, 1),
    })


@app.route("/api/events")
def api_events():
    records = list(EVENT_BUFFER)[-20:]
    records.reverse()  # 最新在前
    return jsonify({"count": len(records), "records": records})


# ---------------- 数据集接口 ----------------


@app.route("/api/dataset")
def api_dataset():
    return jsonify({
        "name": DATASET_NAME,
        "ready": _DS["ready"],
        "total_samples": _DS["total_media"],
        "indexed_samples": _DS["indexed"],
        "truncated": _DS["truncated"],
        "format": _DS["format"],
        "classes": _DS["classes"],
        "note": _DS["note"],
    })


@app.route("/api/dataset/samples")
def api_dataset_samples():
    out = [{
        "id": s["id"],
        "file": s["file"],
        "media_type": s["media_type"],
        "classes": sorted({a["class"] for a in s["annotations"]}),
        "annotation_count": len(s["annotations"]),
    } for s in _DS["samples"][:50]]
    return jsonify({"count": len(out), "samples": out})


@app.route("/api/dataset/sample/<int:sid>")
def api_dataset_sample(sid):
    if sid < 0 or sid >= len(_DS["samples"]):
        abort(404)
    s = _DS["samples"][sid]
    return jsonify({
        "id": s["id"],
        "file": s["file"],
        "media_type": s["media_type"],
        "width": s.get("width"),
        "height": s.get("height"),
        "file_url": "/dataset-file/" + s["file"],
        "annotation_count": len(s["annotations"]),
        "annotations": s["annotations"],
    })


@app.route("/dataset-file/<path:filename>")
def dataset_file(filename):
    # send_from_directory 内部经 safe_join 校验,阻止路径穿越
    return send_from_directory(DATASET_DIR, filename)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/<path:page>")
def static_page(page):
    return send_from_directory(".", page)


if __name__ == "__main__":
    print("=" * 56)
    print("  篮训BOT · 本地实时采集后端(演示用途,未加载 AI 模型)")
    print(f"  实时采集页:  http://{HOST}:{PORT}/camera.html")
    print(f"  网站首页:    http://{HOST}:{PORT}/")
    print(f"  MJPEG 流:    http://{HOST}:{PORT}/video_feed")
    print("=" * 56)
    app.run(host=HOST, port=PORT, threaded=True, debug=False)
