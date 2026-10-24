# -*- coding: utf-8 -*-
"""篮训BOT 本地摄像头采集后端(演示用途,不加载任何 AI 模型)。

- GET /video_feed   MJPEG 摄像头流,摄像头不可用时输出占位帧
- GET /api/status   摄像头状态 / FPS / 分辨率 / 运行时长
- GET /api/events   模拟逐帧事件流(参照 OpenHoopVision basketball_frame_v2 JSONL 格式)
- GET / 与 /<page>.html  静态托管网站页面
"""
import itertools
import random
import threading
import time
from collections import deque

import cv2
import numpy as np
from flask import Flask, Response, jsonify, send_from_directory

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
