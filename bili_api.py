# -*- coding: utf-8 -*-
"""BiliPink Bilibili API client.
No yt-dlp dependency.
Supports normal video streams and DASH audio/video streams.
"""

import json
import re
import urllib.parse
import urllib.request


UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


def _request_json(url, headers=None, timeout=20):
    h = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }

    if headers:
        h.update(headers)

    req = urllib.request.Request(url, headers=h)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")

    data = json.loads(raw)

    if not isinstance(data, dict):
        raise RuntimeError("Bilibili API returned invalid data")

    return data


def normalize_input(text):
    text = (text or "").strip()

    if not text:
        raise ValueError(
            "Please enter a BV number, AV number, or Bilibili video link."
        )

    bv = re.search(r"BV[0-9A-Za-z]{10}", text, re.I)

    if bv:
        return (
            "https://www.bilibili.com/video/"
            + bv.group(0)
        )

    av = re.search(
        r"(?i)(?:av\s*|/video/av)(\d+)",
        text
    )

    if av:
        return (
            "https://www.bilibili.com/video/av"
            + av.group(1)
        )

    short = re.search(
        r"https?://(?:b23\.tv|bili2233\.cn)/[^\s，。；,.;]+",
        text
    )

    if short:
        return short.group(0).rstrip("，。；,.;")

    url = re.search(r"https?://\S+", text)

    if url:
        value = url.group(0).rstrip("，。；,.;")

        if (
            "bilibili.com" in value
            or "b23.tv" in value
            or "bili2233.cn" in value
        ):
            return value

    raise ValueError(
        "No valid BV/AV number or Bilibili link was found."
    )


def resolve_url(text):
    url = normalize_input(text)

    if "b23.tv" in url:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.geturl()
        except Exception:
            raise RuntimeError(
                "Short link expansion failed. "
                "Please use the BV number instead."
            )

    return url


def _extract_ids(url):
    bv = re.search(
        r"BV[0-9A-Za-z]{10}",
        url,
        re.I
    )

    if bv:
        return {
            "bvid": bv.group(0)
        }

    av = re.search(
        r"/video/av(\d+)|av(\d+)",
        url,
        re.I
    )

    if av:
        aid = av.group(1) or av.group(2)

        return {
            "aid": int(aid)
        }

    raise RuntimeError(
        "The video URL does not contain a BV or AV number."
    )


def get_video_info(text):
    url = resolve_url(text)
    ids = _extract_ids(url)

    query = urllib.parse.urlencode(ids)

    api_url = (
        "https://api.bilibili.com/"
        "x/web-interface/view?"
        + query
    )

    data = _request_json(api_url)

    if data.get("code") != 0 or not data.get("data"):
        raise RuntimeError(
            "Failed to get video information: "
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

        "title": d.get(
            "title",
            "BiliPink Video"
        ),

        "owner": owner.get(
            "name",
            "Unknown UP"
        ),

        "mid": owner.get(
            "mid",
            ""
        ),

        "duration": page0.get(
            "duration",
            d.get("duration", 0)
        ),

        "cover": d.get(
            "pic",
            ""
        ),

        "desc": d.get(
            "desc",
            ""
        ),

        "view": stat.get(
            "view",
            0
        ),

        "danmaku": stat.get(
            "danmaku",
            0
        ),

        "like": stat.get(
            "like",
            0
        ),

        "coin": stat.get(
            "coin",
            0
        ),

        "favorite": stat.get(
            "favorite",
            0
        ),

        "reply": stat.get(
            "reply",
            0
        ),

        "pages": pages,

        "url": url
    }


def _quality_label(q):
    quality_map = {
        127: "8K",
        126: "Dolby Vision",
        125: "HDR",
        120: "4K",
        116: "1080P High Bitrate",
        112: "1080P+",
        80: "1080P",
        74: "720P60",
        64: "720P",
        32: "480P",
        16: "360P",
    }

    return quality_map.get(
        int(q),
        "Quality " + str(q)
    )


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
    """Get available Bilibili video streams.

    The function first tries normal MP4 streams.
    If Bilibili returns DASH, it also returns separate
    video and audio streams.
    """

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
        "https://api.bilibili.com/"
        "x/player/playurl?"
        + urllib.parse.urlencode(params)
    )

    data = _request_json(
        url,
        headers=headers,
        timeout=22
    )

    if data.get("code") != 0:
        raise RuntimeError(
            "Failed to get playback URL: "
            + str(data.get("message") or data.get("code"))
        )

    player = data.get("data") or {}

    accept_quality = player.get(
        "accept_quality"
    ) or []

    accept_description = player.get(
        "accept_description"
    ) or []

    labels = {}

    for index, qn in enumerate(accept_quality):
        if index < len(accept_description):
            labels[int(qn)] = accept_description[index]
        else:
            labels[int(qn)] = _quality_label(qn)

    options = []

    # --------------------------------------------------
    # Normal DURL MP4 streams
    # --------------------------------------------------

    durl_list = player.get("durl") or []

    for qn in sorted(
        set(accept_quality),
        reverse=True
    ):
        try:
            qparams = dict(params)
            qparams["qn"] = int(qn)

            qurl = (
                "https://api.bilibili.com/"
                "x/player/playurl?"
                + urllib.parse.urlencode(qparams)
            )

            result = _request_json(
                qurl,
                headers=headers,
                timeout=22
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
                    "label": labels.get(
                        int(qn),
                        _quality_label(qn)
                    ),
                    "url": item["url"],
                    "size": item.get(
                        "size",
                        0
                    ),
                })

        except Exception:
            continue

    # --------------------------------------------------
    # DASH video/audio
    # --------------------------------------------------

    dash = player.get("dash") or {}

    videos = dash.get("video") or []
    audios = dash.get("audio") or []

    if videos and audios:

        video_items = []

        for video in videos:
            video_url = (
                video.get("baseUrl")
                or video.get("base_url")
                or ""
            )

            if not video_url:
                continue

            video_items.append({
                "id": video.get(
                    "id",
                    0
                ),
                "quality": video.get(
                    "id",
                    0
                ),
                "label": labels.get(
                    int(video.get("id", 0)),
                    _quality_label(
                        video.get("id", 0)
                    )
                ),
                "url": video_url,
                "size": video.get(
                    "size",
                    0
                ),
                "bandwidth": video.get(
                    "bandwidth",
                    0
                ),
                "mime_type": video.get(
                    "mimeType",
                    "video/mp4"
                ),
            })

        audio_items = []

        for audio in audios:
            audio_url = (
                audio.get("baseUrl")
                or audio.get("base_url")
                or ""
            )

            if not audio_url:
                continue

            audio_items.append({
                "id": audio.get(
                    "id",
                    0
                ),
                "url": audio_url,
                "size": audio.get(
                    "size",
                    0
                ),
                "bandwidth": audio.get(
                    "bandwidth",
                    0
                ),
                "mime_type": audio.get(
                    "mimeType",
                    "audio/mp4"
                ),
            })

        if video_items and audio_items:

            # Use the highest available audio stream.
            audio_items.sort(
                key=lambda x: (
                    x.get("bandwidth", 0)
                ),
                reverse=True
            )

            best_audio = audio_items[0]

            for video in video_items:
                options.append({
                    "type": "dash",
                    "quality": video["quality"],
                    "label": video["label"] + " + Audio",
                    "url": video["url"],
                    "video_url": video["url"],
                    "audio_url": best_audio["url"],
                    "video_size": video.get(
                        "size",
                        0
                    ),
                    "audio_size": best_audio.get(
                        "size",
                        0
                    ),
                    "size": (
                        video.get("size", 0)
                        + best_audio.get("size", 0)
                    ),
                    "audio": best_audio,
                })

    if not options:
        raise RuntimeError(
            "No downloadable stream was found. "
            "Some videos require a valid Bilibili Cookie."
        )

    # DASH first, then MP4, highest quality first.
    options.sort(
        key=lambda x: (
            1 if x.get("type") == "dash" else 0,
            x.get("quality", 0)
        ),
        reverse=True
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
        "https://api.bilibili.com/"
        "x/web-interface/search/type?"
        + urllib.parse.urlencode(params)
    )

    try:
        data = _request_json(
            url,
            timeout=18
        )
    except Exception:
        return []

    if data.get("code") != 0:
        return []

    result = data.get("data") or {}

    rows = result.get("result") or []

    output = []

    for item in rows:
        if item.get("type") != "video":
            continue

        bvid = item.get("bvid")

        if not bvid:
            continue

        title = re.sub(
            r"<[^>]+>",
            "",
            str(item.get("title", ""))
        )

        duration = item.get(
            "duration",
            "--:--"
        )

        output.append({
            "bvid": bvid,
            "aid": item.get("aid", ""),
            "title": title,
            "author": item.get(
                "author",
                "Unknown"
            ),
            "duration": duration,
            "pubdate": item.get(
                "pubdate",
                ""
            ),
            "play": item.get(
                "play",
                0
            ),
            "description": re.sub(
                r"<[^>]+>",
                "",
                str(item.get("description", ""))
            ),
            "cover": item.get(
                "pic",
                ""
            ),
        })

    return output
