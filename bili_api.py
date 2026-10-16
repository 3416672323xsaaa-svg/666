# -*- coding: utf-8 -*-
"""Minimal Bilibili public API client. No yt‑dlp dependency."""
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
    short = re.search(r"https?://(?:b23\.tv|bili2233\.cn)/[^\s，。；,.;]+", text)
    if short:
        return short.group(0).rstrip("，。；,.;")
    url = re.search(r"https?://\S+", text)
    if url and ("bilibili.com" in url.group(0) or "b23.tv" in url.group(0)):
        return url.group(0).rstrip("，。；,.;")
    raise ValueError("没有识别到有效的 BV/AV 号或 B 站链接")


def resolve_url(text):
    url = normalize_input(text)
    # b23.tv 短链跟随重定向
    if "b23.tv" in url:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                final = resp.geturl()
                return final
        except Exception:
            raise RuntimeError("短链接展开失败！请直接复制BV号使用")
    return url


def _extract_ids(url):
    bv = re.search(r"BV[0-9A-Za-z]{10}", url, re.I)
    av = re.search(r"/video/av(\d+)|av(\d+)", url, re.I)
    if bv:
        return {"bvid": bv.group(0)}
    if av:
        aid_str = av.group(1) or av.group(2)
        return {"aid": int(aid_str)}
    raise RuntimeError("链接内找不到BV/AV编号")


def get_video_info(text):
    url = resolve_url(text)
    ids = _extract_ids(url)
    query = urllib.parse.urlencode(ids)
    api_url = "https://api.bilibili.com/x/web-interface/view?" + query
    data = _request_json(api_url)
    if data.get("code") != 0 or not data.get("data"):
        msg = data.get("message") or f"code={data.get('code')}"
        raise RuntimeError(f"获取视频信息失败：{msg}")
    d = data["data"]
    pages = d.get("pages") or [{}]
    page0 = pages[0]
    return {
        "bvid": d.get("bvid", ""),
        "aid": d.get("aid", ""),
        "cid": page0.get("cid", 0),
        "title": d.get("title", "未命名视频"),
        "owner": (d.get("owner") or {}).get("name", "未知UP主"),
        "mid": (d.get("owner") or {}).get("mid", ""),
        "duration": page0.get("duration", d.get("duration", 0)),
        "cover": d.get("pic", ""),
        "desc": d.get("desc", ""),
        "view": (d.get("stat") or {}).get("view", 0),
        "danmaku": (d.get("stat") or {}).get("danmaku", 0),
        "like": (d.get("stat") or {}).get("like", 0),
        "coin": (d.get("stat") or {}).get("coin", 0),
        "favorite": (d.get("stat") or {}).get("favorite", 0),
        "reply": (d.get("stat") or {}).get("reply", 0),
        "pages": pages,
        "url": url
    }


def _quality_label(q):
    map_q = {
        127:"8K",126:"杜比视界",125:"HDR",120:"4K",
        116:"1080P高码率",112:"1080P+",80:"1080P",
        74:"720P60",64:"720P",32:"480P",16:"360P"
    }
    return map_q.get(int(q), f"画质{q}")


def get_download_options(info, cookie=""):
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    if cookie.strip():
        headers["Cookie"] = cookie.strip()

    def fetch(qn):
        params = {"qn":qn,"fnval":0,"fnver":0,"fourk":1}
        if info.get("bvid"):
            params["bvid"]=info["bvid"]
        else:
            params["avid"]=info["aid"]
        params["cid"]=info["cid"]
        url = "https://api.bilibili.com/x/player/playurl?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=22) as r:
                pl = json.loads(r.read().decode("utf-8","replace"))
            return pl, None
        except Exception as e:
            return None, str(e)

    base, err = fetch(0)
    if err or (base and base.get("code")!=0):
        raise RuntimeError(f"获取播放地址失败：{err or base.get('message')}")
    accept_q = base.get("data",{}).get("accept_quality") or []
    accept_desc = base.get("data",{}).get("accept_description") or []
    label_dict = {}
    for idx,qn in enumerate(accept_q):
        label_dict[int(qn)] = accept_desc[idx] if idx<len(accept_desc) else _quality_label(qn)
    out = []
    for qn in sorted(set(accept_q), reverse=True):
        res, e2 = fetch(qn)
        if not res or res.get("code")!=0:
            continue
        dt = res.get("data",{})
        durl_list = dt.get("durl") or []
        if not durl_list or not durl_list[0].get("url"):
            continue
        out.append({
            "quality": int(qn),
            "label": label_dict.get(int(qn), _quality_label(qn)),
            "url": durl_list[0]["url"],
            "size": durl_list[0].get("size",0)
        })
    if not out:
        raise RuntimeError("该视频无直连MP4流（DASH音画分离暂不支持；可尝试BV号、部分视频需要登录Cookie）")
    return out
