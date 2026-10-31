# -*- coding: utf-8 -*-
"""
qwenAI（千问AI平台）密钥加载器
================================

本文件不含任何密钥，可以放心提交到公开仓库。

真正的 API Key 保存在同目录下的「qwen_api_key」文件中（无扩展名，
已被 .gitignore 忽略，不会被提交）。使用方法：

    1. 在本目录新建一个名为 qwen_api_key 的空文件；
    2. 把你在千问AI平台申请的 API Key 粘贴进去并保存
       （形如 sk-xxxxxxxx，只贴 Key 本身，不要加引号）；
    3. 重新运行「语音识别GUI.py」即可生效。

获取 Key：登录 https://platform.qianwenai.com -> 右上角「工作台」-> API Key。
"""

import os

# ================= 密钥（从外部文件读取，一般不用修改本区域） =================

_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_api_key")

if os.path.exists(_KEY_FILE):
    with open(_KEY_FILE, "r", encoding="utf-8") as _f:
        QWEN_API_KEY = _f.read().strip()
else:
    QWEN_API_KEY = ""

# ================= 以下一般不用修改 =================

# API 服务地址（千问AI平台）
QWEN_BASE_URL = "https://maas.qianwenaiapi.com/api/v1"

# 语音识别模型
QWEN_ASR_MODEL = "qwen3-asr-flash-filetrans"
