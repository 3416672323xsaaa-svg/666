# -*- coding: utf-8 -*-
"""Minimal Bilibili public API client. No yt-dlp dependency."""
import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36")


def _request_json(url, timeout=18):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("B站接口返回了无法识别的数据")
    return data


def normalize_input(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("请先输入 BV 号、AV 号或视频链接")
    bv = re.search(r"BV[0-9A-Za-z]{10}", text, re.I)
    if bv:
        return "https://www.bilibili.com/video/" + bv.group(0)
    av = re.search(r"(?i)(?:av\s*|/video/av)(\d+)", text)
    if av:
        return "https://www.bilibili.com/video/av" + av.group(1)
    short = re.search(r"https?://(?:b23\.tv|bili2233\.cn)/\S+", text)
    if short:
        return short.group(0).rstrip("，。；,.;")
    url = re.search(r"https?://\S+", text)
    if url and ("bilibili.com" in url.group(0) or "b23.tv" in url.group(0)):
        return url.group(0).rstrip("，。；,.;")
    raise ValueError("没有识别到有效的 BV/AV 号或 B 站链接")


def resolve_url(text):
    url = normalize_input(text)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            url = resp.geturl()
    except Exception:
        # A failed short-link expansion will be reported by the following parse step.
        if "b23.tv" in url:
            raise RuntimeError("短链接展开失败，请改用 BV 号或完整视频链接")
    return url


def _extract_ids(url):
    bv = re.search(r"BV[0-9A-Za-z]{10}", url, re.I)
    av = re.search(r"/video/av(\d+)|\bav(\d+)\b", url, re.I)
    if bv:
        return {"bvid": bv.group(0)}
    if av:
        return {"aid": int(av.group(1) or av.group(2))}
    raise RuntimeError("链接中没有找到 BV/AV 视频编号")


def get_video_info(text):
    url = resolve_url(text)
    ids = _extract_ids(url)
    query = urllib.parse.urlencode(ids)
    data = _request_json("https://api.bilibili.com/x/web-interface/view?" + query)
    if data.get("code") != 0 or not data.get("data"):
        raise RuntimeError("获取视频信息失败：" + str(data.get("message") or data.get("code")))
    d = data["data"]
    pages = d.get("pages") or [{}]
    page = pages[0]
    return {
        "bvid": d.get("bvid", ""), "aid": d.get("aid", ""),
        "cid": page.get("cid", ""), "title": d.get("title", "未命名视频"),
        "owner": (d.get("owner") or {}).get("name", "未知 UP 主"),
        "mid": (d.get("owner") or {}).get("mid", ""),
        "duration": page.get("duration", d.get("duration", 0)),
        "cover": d.get("pic", ""), "desc": d.get("desc", ""),
        "view": (d.get("stat") or {}).get("view", 0),
        "danmaku": (d.get("stat") or {}).get("danmaku", 0),
        "like": (d.get("stat") or {}).get("like", 0),
        "coin": (d.get("stat") or {}).get("coin", 0),
        "favorite": (d.get("stat") or {}).get("favorite", 0),
        "reply": (d.get("stat") or {}).get("reply", 0),
        "share": (d.get("stat") or {}).get("share", 0),
        "pages": pages, "url": url,
    }


def get_download_options(info, cookie=""):
    """Return only API-confirmed direct MP4 streams; DASH-only sources are not misreported."""
    headers = {"User-Agent": UA, "Referer": info.get("url", "https://www.bilibili.com/")}
    if cookie.strip():
        headers["Cookie"] = cookie.strip()

    def fetch(qn):
        params = {
            "avid": info.get("aid", ""), "cid": info.get("cid", ""),
            "qn": int(qn), "fnval": 0, "fnver": 0, "fourk": 1,
        }
        if info.get("bvid"):
            params["bvid"] = info["bvid"]
        url = "https://api.bilibili.com/x/player/playurl?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        if payload.get("code") != 0:
            return None, payload.get("message") or payload.get("code")
        return payload.get("data") or {}, None

    # qn=0 asks the API for its default permitted stream. Requesting 127 first
    # wrongly fails for ordinary videos/accounts that cannot access 8K.
    base, error = fetch(0)
    if error:
        raise RuntimeError("获取下载地址失败：" + str(error) + "。部分画质需要登录或账号权限。")
    accepted = base.get("accept_quality") or [base.get("quality", 0)]
    descs = base.get("accept_description") or []
    labels = {int(q): str(descs[i]) if i < len(descs) else _quality_label(int(q))
              for i, q in enumerate(accepted) if str(q).isdigit()}
    options = []
    for qn in sorted({int(q) for q in accepted if str(q).isdigit()}, reverse=True):
        data, err = fetch(qn)
        if not data:
            continue
        streams = data.get("durl") or []
        if not streams or not streams[0].get("url"):
            continue
        options.append({
            "quality": int(data.get("quality") or qn),
            "label": labels.get(qn, _quality_label(qn)),
            "url": streams[0]["url"],
            "size": streams[0].get("size", 0),
            "length": streams[0].get("length", 0),
        })
    if not options:
        raise RuntimeError("B站没有返回可直接下载的 MP4 视频流。该视频可能只提供 DASH 分离音视频，当前版本暂不支持合并；也可能需要登录或更高账号权限。")
    return options

def _quality_label(q):
    return {127: "8K", 126: "杜比视界", 125: "HDR", 120: "4K", 116: "1080P 高码率", 112: "1080P+", 80: "1080P", 74: "720P60", 64: "720P", 32: "480P", 16: "360P"}.get(q, "画质代码 " + str(q))
