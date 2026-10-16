# -*- coding: utf-8 -*-
"""Reliable direct MP4 stream downloader. Filenames preserve Chinese Unicode."""
import os
import re
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36")


def safe_filename(name):
    # Keep Chinese/Japanese/Korean characters; remove only filesystem-reserved chars.
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name or "BiliPink_video"))
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name or "BiliPink_video")[:100]


def download_stream(url, output_path, progress=None, cancel_check=None):
    parent = os.path.dirname(output_path) or "."
    os.makedirs(parent, exist_ok=True)
    temp_path = output_path + ".part"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "video/mp4,application/octet-stream,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError("视频服务器返回 HTTP 状态：" + str(status))
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type or "application/json" in content_type:
                raise RuntimeError("服务器返回了网页或错误信息，不是视频文件。请重新解析，或检查视频权限。")
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(temp_path, "wb") as out:
                while True:
                    if cancel_check and cancel_check():
                        raise InterruptedError("下载已取消")
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        if done < 1024:
            raise RuntimeError("下载内容异常或文件过小，未保存为有效视频。")
        os.replace(temp_path, output_path)
        return output_path
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise
