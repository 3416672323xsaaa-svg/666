# -*- coding: utf-8 -*-
"""BiliPink Bilibili API client. No yt-dlp dependency."""

import json
import re
import ssl
import certifi
import urllib.parse
import urllib.request
import os


UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


def _ssl_context():
    """优先使用 certifi 的 CA 证书；失败时再尝试系统证书。"""
    try:
        ca_file = certifi.where()
        if ca_file and os.path.isfile(ca_file):
            return ssl.create_default_context(cafile=ca_file)
    except Exception as exc:
        print("[BiliPink] certifi CA 加载失败：", exc)

    try:
        return ssl.create_default_context()
    except Exception as exc:
        raise RuntimeError(
            "无法加载 HTTPS 根证书。请检查 APK 是否正确打包 certifi。"
            + str(exc)
        ) from exc


def _request_json(url, headers=None, timeout=20):
    h = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }

    if headers:
        h.update(headers)

    req = urllib.request.Request(url, headers=h)

    try:
        with urllib.request.urlopen(
            req,
            timeout=timeout,
            context=_ssl_context(),
        ) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except Exception as exc:
        raise RuntimeError(
            "B站 HTTPS 请求失败：" + str(exc)
        ) from exc

    try:
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(
            "B站返回的不是有效 JSON 数据"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("B站接口返回了无效数据")

    return data


def normalize_input(text):
    """识别 BV、AV、B站短链接及普通视频链接。"""
    text = (text or "").strip()

    if not text:
        raise ValueError("请输入 BV 号、AV 号或 B 站视频链接。")

    bv = re.search(r"BV[0-9A-Za-z]{10}", text, re.I)
    if bv:
        return "https://www.bilibili.com/video/" + bv.group(0)

    av = re.search(
        r"(?i)(?:^|[^A-Za-z0-9])av\s*(\d+)(?!\d)",
        text,
    )
    if av:
        return "https://www.bilibili.com/video/av" + av.group(1)

    short = re.search(
        r"https?://(?:b23\.tv|bili2233\.cn)/[^\s，。；,.;]+",
        text,
        re.I,
    )
    if short:
        return short.group(0).rstrip("，。；,.;")

    url = re.search(r"https?://\S+", text, re.I)
    if url:
        value = url.group(0).rstrip("，。；,.;")
        if any(
            host in value.lower()
            for host in (
                "bilibili.com",
                "b23.tv",
                "bili2233.cn",
            )
        ):
            return value

    raise ValueError("没有找到有效的 BV/AV 号或 B 站链接。")


def resolve_url(text):
    url = normalize_input(text)

    if "b23.tv" in url.lower() or "bili2233.cn" in url.lower():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(
                req,
                timeout=15,
                context=_ssl_context(),
            ) as resp:
                return resp.geturl()
        except Exception as exc:
            raise RuntimeError(
                "B站短链接展开失败：" + str(exc)
                + "。请尝试直接输入 BV 号或 AV 号。"
            ) from exc

    return url


def _extract_ids(url):
    bv = re.search(r"BV[0-9A-Za-z]{10}", url, re.I)
    if bv:
        return {"bvid": bv.group(0)}

    av = re.search(r"/video/av(\d+)|av(\d+)", url, re.I)
    if av:
        return {"aid": int(av.group(1) or av.group(2))}

    raise RuntimeError("链接中没有找到 BV 或 AV 编号。")


def get_video_info(text):
    url = resolve_url(text)
    ids = _extract_ids(url)
    query = urllib.parse.urlencode(ids)

    api_url = (
        "https://api.bilibili.com/"
        "x/web-interface/view?" + query
    )
    data = _request_json(api_url)

    if data.get("code") != 0 or not data.get("data"):
        raise RuntimeError(
            "获取视频信息失败："
            + str(data.get("message") or data.get("code"))
        )

    d = data["data"]
    pages = d.get("pages") or [{}]
    page0 = pages[0]
    stat = d.get("stat") or {}
    owner = d.get("owner") or {}

    return {
        "bvid": d.get("bvid", ""),
        "aid": d.get("aid", ""),
        "cid": page0.get("cid", 0),
        "title": d.get("title", "BiliPink Video"),
        "owner": owner.get("name", "Unknown UP"),
        "mid": owner.get("mid", ""),
        "duration": page0.get("duration", d.get("duration", 0)),
        "cover": d.get("pic", ""),
        "desc": d.get("desc", ""),
        "view": stat.get("view", 0),
        "danmaku": stat.get("danmaku", 0),
        "like": stat.get("like", 0),
        "coin": stat.get("coin", 0),
        "favorite": stat.get("favorite", 0),
        "reply": stat.get("reply", 0),
        "pages": pages,
        "url": url,
    }


def _quality_label(q):
    quality_map = {
        127: "8K",
        126: "Dolby Vision",
        125: "HDR",
        120: "4K",
        116: "1080P 高码率",
        112: "1080P+",
        80: "1080P",
        74: "720P60",
        64: "720P",
        32: "480P",
        16: "360P",
    }
    return quality_map.get(int(q), "Quality " + str(q))


def _make_headers(cookie=""):
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }
    if cookie:
        headers["Cookie"] = cookie.strip()
    return headers


def get_download_options(info, cookie=""):
    """获取可用的视频流，支持 MP4 和 DASH 音视频流。"""
    headers = _make_headers(cookie)
    params = {
        "cid": info["cid"],
        "fnval": 4048,
        "fnver": 0,
        "fourk": 1,
    }

    if info.get("bvid"):
        params["bvid"] = info["bvid"]
    else:
        params["avid"] = info["aid"]

    url = (
        "https://api.bilibili.com/x/player/playurl?"
        + urllib.parse.urlencode(params)
    )
    data = _request_json(url, headers=headers, timeout=22)

    if data.get("code") != 0:
        raise RuntimeError(
            "获取播放地址失败："
            + str(data.get("message") or data.get("code"))
        )

    player = data.get("data") or {}
    accept_quality = player.get("accept_quality") or []
    accept_description = player.get("accept_description") or []

    labels = {}
    for index, qn in enumerate(accept_quality):
        if index < len(accept_description):
            labels[int(qn)] = accept_description[index]
        else:
            labels[int(qn)] = _quality_label(qn)

    options = []

    # 普通 MP4 视频流
    for qn in sorted(set(accept_quality), reverse=True):
        try:
            qparams = dict(params)
            qparams["qn"] = int(qn)
            qurl = (
                "https://api.bilibili.com/x/player/playurl?"
                + urllib.parse.urlencode(qparams)
            )
            result = _request_json(
                qurl,
                headers=headers,
                timeout=22,
            )

            if result.get("code") != 0:
                continue

            pdata = result.get("data") or {}
            durls = pdata.get("durl") or []

            if durls and durls[0].get("url"):
                item = durls[0]
                options.append({
                    "type": "mp4",
                    "quality": int(qn),
                    "label": labels.get(int(qn), _quality_label(qn)),
                    "url": item["url"],
                    "size": item.get("size", 0),
                })
        except Exception:
            continue

    # DASH 分离的视频流和音频流
    dash = player.get("dash") or {}
    videos = dash.get("video") or []
    audios = dash.get("audio") or []

    if videos and audios:
        video_items = []

        for video in videos:
            video_url = video.get("baseUrl") or video.get("base_url") or ""
            if not video_url:
                continue

            q = int(video.get("id", 0))
            video_items.append({
                "id": q,
                "quality": q,
                "label": labels.get(q, _quality_label(q)),
                "url": video_url,
                "size": video.get("size", 0),
                "bandwidth": video.get("bandwidth", 0),
                "mime_type": video.get("mimeType", "video/mp4"),
            })

        audio_items = []
        for audio in audios:
            audio_url = audio.get("baseUrl") or audio.get("base_url") or ""
            if not audio_url:
                continue

            audio_items.append({
                "id": audio.get("id", 0),
                "url": audio_url,
                "size": audio.get("size", 0),
                "bandwidth": audio.get("bandwidth", 0),
                "mime_type": audio.get("mimeType", "audio/mp4"),
            })

        if video_items and audio_items:
            audio_items.sort(
                key=lambda x: x.get("bandwidth", 0),
                reverse=True,
            )
            best_audio = audio_items[0]

            for video in video_items:
                options.append({
                    "type": "dash",
                    "quality": video["quality"],
                    "label": video["label"] + " + 音频",
                    "url": video["url"],
                    "video_url": video["url"],
                    "audio_url": best_audio["url"],
                    "video_size": video.get("size", 0),
                    "audio_size": best_audio.get("size", 0),
                    "size": (
                        video.get("size", 0)
                        + best_audio.get("size", 0)
                    ),
                    "audio": best_audio,
                })

    if not options:
        raise RuntimeError(
            "没有找到可下载的视频流。部分视频可能需要有效的 B 站 Cookie。"
        )

    options.sort(
        key=lambda x: (
            1 if x.get("type") == "dash" else 0,
            x.get("quality", 0),
        ),
        reverse=True,
    )
    return options


def bilibili_search(keyword, page=1, page_size=10):
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    params = {
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
    }
    url = (
        "https://api.bilibili.com/x/web-interface/search/type?"
        + urllib.parse.urlencode(params)
    )

    data = _request_json(url, timeout=18)

    if data.get("code") != 0:
        code = data.get("code")
        message = str(data.get("message") or "未知错误")

        if code in (-412, -352):
            raise RuntimeError(
                "B站搜索触发风控，请稍后重试。"
                + " 接口错误：" + str(code) + "，" + message
            )

        raise RuntimeError(
            "B站搜索接口错误：" + str(code) + "，" + message
        )

    result = data.get("data") or {}
    rows = result.get("result") or []
    output = []

    for item in rows:
        if item.get("type") != "video":
            continue

        bvid = item.get("bvid")
        if not bvid:
            continue

        output.append({
            "bvid": bvid,
            "aid": item.get("aid", ""),
            "title": re.sub(
                r"<[^>]+>", "", str(item.get("title", ""))
            ),
            "author": item.get("author", "Unknown"),
            "duration": item.get("duration", "--:--"),
            "pubdate": item.get("pubdate", ""),
            "play": item.get("play", 0),
            "description": re.sub(
                r"<[^>]+>", "",
                str(item.get("description", ""))
            ),
            "cover": item.get("pic", ""),
        })

    return output
