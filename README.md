# 语音识别（千问 ASR） | Speech Recognition (Qwen ASR)

> 基于千问AI平台语音识别模型（`qwen3-asr-flash-filetrans`）的桌面小程序：录音或选择 WAV 文件 → 上传云端转写 → 在 GUI 中显示识别结果。界面使用 Python 标准库 tkinter。

**简体中文** · [ English](#english)

---

## 功能特性

- 按住 F 键说话，松开自动识别；结果带时间戳逐条显示在窗口下方。
- 识别流程：录音（16kHz/16bit/单声道）→ 上传平台临时存储（48 小时有效）→ 提交异步转写任务 → 轮询至完成 → 提取文本。
- 密钥通过外部文件加载，代码仓库中不含任何私人凭据。

## 快速开始

### 环境要求

- Python 3.10 及以上（本项目在 3.12 下开发）
- 一个千问AI平台账号（用于申请 API Key）

### 安装依赖

```bash
pip install -r requirements.txt
```

即 `pyaudio` 与 `requests` 两项。Windows 下若 `pyaudio` 安装失败，可用 `pip install pipwin && pipwin install pyaudio`，或下载对应 Python 版本的预编译 wheel。

### 第 1 步：申请 API Key

1. 登录 [千问AI平台](https://platform.qianwenai.com)；
2. 进入右上角「工作台」→「API Key」，创建并复制你的 Key（形如 `sk-xxxxxxxx`）。

### 第 2 步：粘贴你的 API Key

1. 在项目根目录新建一个**无扩展名**的空文件，命名为 `qwen_api_key`（Windows 资源管理器中可先命名 `qwen_api_key.txt` 再删掉 `.txt`）；
2. 用记事本打开，把 API Key **粘贴进去并保存**（只贴 Key 本身，不要加引号或其他文字）；
3. 该文件已被 `.gitignore` 忽略，永远不会被提交到 GitHub。

程序运行时由 `qwen_api_key.py`（加载器，可提交）自动读取这个文件。

### 第 3 步：运行

```bash
python 语音识别GUI.py
```

在界面中录音或选择 WAV 文件，点击开始识别即可。

> 若提示未找到 Key，请确认：文件名恰好是 `qwen_api_key`（没有 `.txt` 后缀）、与 `语音识别GUI.py` 在同一目录、Key 单独占一行且首尾没有多余空格。

## 说明

`qwen_api_key` 属于私人凭据。把它写进公开仓库等于把你的 API 额度公开给所有人，因此本仓库通过 `.gitignore` 永久忽略它——每位使用者按第 2 步自己创建即可。

---

# English

> A small desktop app built on the Qwen AI platform's ASR model (`qwen3-asr-flash-filetrans`): record or pick a WAV file → cloud transcription → results shown in the GUI. The UI uses Python's built-in tkinter.

## Features

- Hold `F` to speak; recognition runs automatically on release, with timestamped results listed below.
- Pipeline: recording (16kHz/16bit/mono) → upload to temporary platform storage (valid 48h) → async transcription task → poll until done → extract text.
- The API key is loaded from an external file — the repository contains no private credentials.

## Quick Start

### Requirements

- Python 3.10+ (developed on 3.12)
- A Qwen AI platform account (to obtain an API key)

### Install dependencies

```bash
pip install -r requirements.txt
```

That is just `pyaudio` and `requests`. On Windows, if `pyaudio` fails to install, use `pip install pipwin && pipwin install pyaudio`, or grab a prebuilt wheel for your Python version.

### Step 1: Get an API key

1. Log in to the [Qwen AI platform](https://platform.qianwenai.com);
2. Go to the top-right Workspace → API Keys, then create and copy your key (looks like `sk-xxxxxxxx`).

### Step 2: Paste your key

1. Create an **extensionless** file named `qwen_api_key` in the project root (name it `qwen_api_key.txt` in Explorer first, then remove `.txt`);
2. Open it in Notepad, **paste the key and save** (the key alone — no quotes, no extra text);
3. This file is gitignored and will never be committed to GitHub.

At runtime the key is read by `qwen_api_key.py` (the loader, which is committed).

### Step 3: Run

```bash
python 语音识别GUI.py
```

Record or choose a WAV file in the UI, then start recognition.

> If the key is not found, check that: the filename is exactly `qwen_api_key` (no `.txt` suffix), it sits next to `语音识别GUI.py`, and the key is on a single line with no stray spaces.

## Notes

`qwen_api_key` is a private credential; committing it to a public repository would expose your API quota to everyone. That is why it is permanently gitignored — each user creates their own as in step 2.
