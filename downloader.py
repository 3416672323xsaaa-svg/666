# -*- coding: utf-8 -*-
"""BiliPink downloader，纯urllib实现，无yt‑dlp"""
import os
import re
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36")


def safe_filename(name):
    name = str(name or "BiliPink视频")
    name = re.sub(r'[\\/:*?"<>|\x00-\x1F]', "_", name)
    name = re.sub(r'\s+', " ", name).strip(" .")
    if len(name) > 96:
        name = name[:96]
    return name or "BiliPink视频"


def download_stream(url, output_path, progress=None, cancel_check=None):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    temp = output_path + ".part"
    # B站直链必须带Referer，否则403
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "*/*"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=48) as rsp:
            status = getattr(rsp, "status",200)
            if not (200 <= status <300):
                raise RuntimeError(f"HTTP {status} 被B站拒绝（链接过期/防盗链）")
            ctype = (rsp.headers.get("Content-Type") or "").lower()
            if "text/html" in ctype or "application/json" in ctype:
                raise RuntimeError("返回不是视频！解析出来的下载链接已失效，请重新解析一次视频")
            total = int(rsp.headers.get("Content-Length") or 0)
            done = 0
            with open(temp, "wb") as f:
                while True:
                    if cancel_check and cancel_check():
                        raise InterruptedError("用户取消下载")
                    chunk = rsp.read(256*1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
        if done <= 1024:
            raise RuntimeError("下载得到文件太小，可能中断或链接失效")
        os.replace(temp, output_path)
        return output_path
    except Exception:
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except Exception:
            pass
        raise
