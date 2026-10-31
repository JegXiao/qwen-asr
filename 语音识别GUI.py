# -*- coding: utf-8 -*-
"""
语音识别 GUI —— 真实调用 qwenAI（千问AI平台）的 qwen3-asr-flash-filetrans 语音识别模型

使用方法：
  1. 把你的 API Key 粘贴到同目录下的 qwen_api_key 文件中（无扩展名，
     详见 README.md；密钥由 qwen_api_key.py 加载器读取）；
  2. 运行本程序，按住 F 键说话，松开后自动识别，结果显示在窗口下方。

识别流程（全程真实调用，无模拟）：
  录音（16kHz/16bit/单声道 WAV）
    -> 上传到平台免费临时存储，得到 oss:// 临时 URL（有效期 48 小时）
    -> 提交 qwen3-asr-flash-filetrans 异步转写任务
    -> 轮询任务状态直到 SUCCEEDED
    -> 下载转写结果 JSON，提取文字显示
"""

import json
import os
import queue
import tempfile
import threading
import time
import wave
import tkinter as tk
from tkinter import scrolledtext

import pyaudio
import requests

# ======================== 配置（来自 qwen_api_key.py） ========================

_DEFAULT_BASE_URL = "https://maas.qianwenaiapi.com/api/v1"
_DEFAULT_MODEL = "qwen3-asr-flash-filetrans"

try:
    from qwen_api_key import QWEN_API_KEY, QWEN_BASE_URL, QWEN_ASR_MODEL

    API_KEY = (QWEN_API_KEY or "").strip()
    BASE_URL = (QWEN_BASE_URL or _DEFAULT_BASE_URL).strip().rstrip("/")
    ASR_MODEL = (QWEN_ASR_MODEL or _DEFAULT_MODEL).strip()
    CONFIG_IMPORTED = True
except ImportError:
    API_KEY = ""
    BASE_URL = _DEFAULT_BASE_URL
    ASR_MODEL = _DEFAULT_MODEL
    CONFIG_IMPORTED = False

# ======================== 录音/识别参数 ========================

MIC_DEVICE_INDEX = 1        # 麦克风设备编号（沿用原程序，换电脑可自行调整）
LANGUAGE = "zh"             # 指定识别语言；改成 "" 则由模型自动检测
POLL_TIMEOUT = 180          # 单次识别最长等待秒数
MIN_RECORD_SECONDS = 0.4    # 短于该时长的录音不提交识别

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

IDLE_TEXT = "待机 - 按住 F 说话"


# ======================== 千问 API 调用 ========================

class QwenASRError(Exception):
    """识别流程中的可展示错误。"""


def upload_audio(api_key, wav_path):
    """上传本地录音到平台临时存储，返回 oss:// 临时 URL（有效期 48 小时）。"""
    # 1) 获取上传凭证（注意：model 必须与后续调用的模型一致）
    resp = requests.get(
        f"{BASE_URL}/uploads",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        params={"action": "getPolicy", "model": ASR_MODEL},
        timeout=30,
    )
    if resp.status_code != 200:
        raise QwenASRError(f"获取上传凭证失败 HTTP {resp.status_code}: {resp.text[:200]}")
    policy = resp.json().get("data") or {}

    required = ("policy", "signature", "upload_dir", "upload_host",
                "oss_access_key_id", "x_oss_object_acl", "x_oss_forbid_overwrite")
    missing = [k for k in required if k not in policy]
    if missing:
        raise QwenASRError(f"上传凭证缺少字段 {missing}，响应: {str(policy)[:200]}")

    file_name = os.path.basename(wav_path)
    key = f"{policy['upload_dir']}/{file_name}"

    # 2) 以表单方式上传文件（file 必须是最后一个表单域）
    with open(wav_path, "rb") as f:
        files = {
            "OSSAccessKeyId": (None, policy["oss_access_key_id"]),
            "Signature": (None, policy["signature"]),
            "policy": (None, policy["policy"]),
            "x-oss-object-acl": (None, policy["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy["x_oss_forbid_overwrite"]),
            "key": (None, key),
            "success_action_status": (None, "200"),
            "file": (file_name, f),
        }
        up = requests.post(policy["upload_host"], files=files, timeout=120)
    if up.status_code != 200:
        raise QwenASRError(f"音频上传失败 HTTP {up.status_code}: {up.text[:200]}")

    return f"oss://{key}"


def submit_task(api_key, file_url):
    """提交异步转写任务，返回 task_id。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    if file_url.startswith("oss://"):
        # 使用 oss:// 临时 URL 必须携带该请求头，否则服务端无法解析
        headers["X-DashScope-OssResourceResolve"] = "enable"

    parameters = {
        "channel_id": [0],
        "enable_itn": True,     # 数字/日期规范化（如 "二零二五" -> "2025"）
        "enable_words": False,  # 句级时间戳即可，不需要字级
    }
    if LANGUAGE:
        parameters["language"] = LANGUAGE

    payload = {
        "model": ASR_MODEL,
        "input": {"file_url": file_url},
        "parameters": parameters,
    }
    resp = requests.post(
        f"{BASE_URL}/services/audio/asr/transcription",
        headers=headers, json=payload, timeout=30,
    )
    if resp.status_code != 200:
        raise QwenASRError(f"任务提交失败 HTTP {resp.status_code}: {resp.text[:300]}")
    task_id = (resp.json().get("output") or {}).get("task_id")
    if not task_id:
        raise QwenASRError(f"提交响应中没有 task_id: {resp.text[:300]}")
    return task_id


def wait_task(api_key, task_id):
    """轮询任务状态直到结束，成功时返回任务 output。"""
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + POLL_TIMEOUT
    interval = 1.0
    while True:
        time.sleep(interval)
        resp = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers, timeout=30)
        if resp.status_code != 200:
            raise QwenASRError(f"任务查询失败 HTTP {resp.status_code}: {resp.text[:200]}")
        output = resp.json().get("output") or {}
        status = str(output.get("task_status", "")).upper()
        if status == "SUCCEEDED":
            return output
        if status in ("FAILED", "UNKNOWN"):
            detail = output.get("message") or output.get("code") or status
            raise QwenASRError(f"识别任务失败: {detail}")
        if time.time() >= deadline:
            raise QwenASRError(f"识别超时（>{POLL_TIMEOUT}s），task_id={task_id}")
        interval = min(interval + 0.5, 3.0)


def download_result(output):
    """从任务结果中取 transcription_url 并下载识别结果 JSON（兼容多种返回结构）。"""
    url = None
    result = output.get("result")
    if isinstance(result, dict):
        url = result.get("transcription_url")
    if not url:
        results = output.get("results")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            url = results[0].get("transcription_url")
    if not url:
        url = output.get("transcription_url")
    if url:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            raise QwenASRError(f"识别结果下载失败 HTTP {resp.status_code}")
        return resp.json()
    return output  # 个别情况下结果直接内嵌在 output 中


def extract_text(data):
    """从转写结果 JSON 中提取纯文本。"""
    parts = []
    for tr in data.get("transcripts") or []:
        text = (tr.get("text") or "").strip()
        if text:
            parts.append(text)
            continue
        for sent in tr.get("sentences") or []:
            t = (sent.get("text") or "").strip()
            if t:
                parts.append(t)
    if not parts:
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "".join(parts).strip()


def recognize_wav(api_key, wav_path, progress=None):
    """完整识别流程：上传 -> 提交 -> 轮询 -> 下载 -> 提取文本。"""
    def report(msg):
        if progress:
            progress(msg)

    report("上传音频...")
    file_url = upload_audio(api_key, wav_path)
    report("提交识别任务...")
    task_id = submit_task(api_key, file_url)
    report("识别中...")
    output = wait_task(api_key, task_id)
    result_json = download_result(output)
    return extract_text(result_json)


# ======================== 录音 ========================

recording = False
frames = []
lock = threading.Lock()
pa = None
stream = None


def _record_thread(rec_stream):
    """后台线程：持续读取麦克风数据到 frames。"""
    while recording:
        try:
            data = rec_stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception:
            break


def start_recording():
    global recording, frames, stream, pa
    with lock:
        if recording:
            return
        recording = True
        frames = []
    try:
        if pa is None:
            pa = pyaudio.PyAudio()
        stream = pa.open(
            format=FORMAT, channels=CHANNELS, rate=RATE,
            input=True, input_device_index=MIC_DEVICE_INDEX,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        with lock:
            recording = False
        show_flash(f"无法打开麦克风: {e}", "red", 4000)
        return
    status_label.config(text="正在录音... 松开 F 停止", fg="red")
    threading.Thread(target=_record_thread, args=(stream,), daemon=True).start()


def stop_recording():
    global recording
    with lock:
        recording = False


def save_wav(audio_bytes, path):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # paInt16 = 2 字节
        wf.setframerate(RATE)
        wf.writeframes(audio_bytes)


def process_audio():
    """松开 F 后：停止录音流，保存 WAV，交给后台识别。"""
    global frames, stream, pending
    with lock:
        data = b"".join(frames)
        frames = []
    if stream is not None:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        stream = None

    seconds = len(data) / (RATE * 2)  # 16bit 单声道
    if seconds < MIN_RECORD_SECONDS:
        show_flash("录音太短，请按住 F 说话", "orange", 1500)
        return

    fd, wav_path = tempfile.mkstemp(prefix="qwen_asr_", suffix=".wav")
    os.close(fd)
    save_wav(data, wav_path)

    pending += 1
    status_label.config(text="上传音频...", fg="blue")
    threading.Thread(target=recognize_worker, args=(wav_path,), daemon=True).start()


# ======================== 后台识别 + UI 队列 ========================

ui_queue = queue.Queue()
pending = 0        # 正在进行中的识别任务数
flash_until = 0.0  # 临时状态展示的截止时间


def recognize_worker(wav_path):
    """后台线程：完整识别流程，结果通过 ui_queue 回传主线程。"""
    try:
        if not CONFIG_IMPORTED:
            raise QwenASRError("找不到 qwen_api_key.py，请先在同目录创建该配置文件")
        if not API_KEY:
            raise QwenASRError("请先把 API Key 粘贴到同目录的 qwen_api_key 文件中（无扩展名）")

        def progress(msg):
            ui_queue.put(("status", msg, "blue"))

        text = recognize_wav(API_KEY, wav_path, progress)
        if text:
            ui_queue.put(("result", text))
        else:
            ui_queue.put(("flash", "未识别到语音内容", "orange", 1500))
    except Exception as e:
        msg = str(e) if isinstance(e, QwenASRError) else f"{type(e).__name__}: {e}"
        ui_queue.put(("flash", f"识别失败: {msg}", "red", 5000))
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass
        ui_queue.put(("done",))


def show_flash(text, color, ms):
    """短暂展示一条状态信息，到期后自动回到待机文案。"""
    global flash_until
    flash_until = time.time() + ms / 1000.0
    status_label.config(text=text, fg=color)
    root.after(ms, reset_status_if_idle)


def reset_status_if_idle():
    if pending <= 0 and not recording and time.time() >= flash_until:
        status_label.config(text=IDLE_TEXT, fg="black")


def append_result(text):
    ts = time.strftime("%H:%M:%S")
    result_text.config(state="normal")
    result_text.insert(tk.END, f"[{ts}] {text}\n")
    result_text.see(tk.END)
    result_text.config(state="disabled")


def poll_ui_queue():
    global pending
    try:
        while True:
            msg = ui_queue.get_nowait()
            kind = msg[0]
            if kind == "status":
                status_label.config(text=msg[1], fg=msg[2])
            elif kind == "result":
                append_result(msg[1])
            elif kind == "flash":
                show_flash(msg[1], msg[2], msg[3])
            elif kind == "done":
                pending = max(0, pending - 1)
                reset_status_if_idle()
    except queue.Empty:
        pass
    root.after(100, poll_ui_queue)


# ======================== 按键绑定 ========================

def on_key_press(event):
    if event.keysym.lower() == "f":
        start_recording()
        return "break"


def on_key_release(event):
    if event.keysym.lower() == "f":
        stop_recording()
        root.after(300, process_audio)  # 延迟 300ms，确保尾部音频已读完
        return "break"


def on_closing():
    stop_recording()
    root.destroy()


# ======================== 窗口 ========================

root = tk.Tk()
root.title(f"语音识别（按住 F 说话）- {ASR_MODEL}")
root.geometry("700x500")
root.protocol("WM_DELETE_WINDOW", on_closing)

title_label = tk.Label(root, text="qwenAI 语音识别", font=("微软雅黑", 18, "bold"))
title_label.pack(pady=10)

status_label = tk.Label(root, text=IDLE_TEXT, font=("微软雅黑", 14))
status_label.pack(pady=15)

hint_label = tk.Label(
    root,
    text="按住 F 键录音，松开后自动识别（模型：qwen3-asr-flash-filetrans）",
    fg="gray", font=("微软雅黑", 10),
)
hint_label.pack()

result_text = scrolledtext.ScrolledText(root, font=("微软雅黑", 11), height=18, state="disabled")
result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

root.bind("<KeyPress>", on_key_press)
root.bind("<KeyRelease>", on_key_release)

# 启动时检查 API Key 配置
if not CONFIG_IMPORTED:
    status_label.config(text="缺少配置文件 qwen_api_key.py，请先创建", fg="red")
elif not API_KEY:
    status_label.config(text="请先把 API Key 粘贴到 qwen_api_key 文件中", fg="red")

root.after(100, poll_ui_queue)
root.mainloop()
