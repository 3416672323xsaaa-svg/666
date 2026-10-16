-- coding: utf-8 --

"""BiliPink Bilibili API client.
Pure urllib implementation.
No yt-dlp / no BDL dependency.
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

REFERER = "https://www.bilibili.com/"

def _request_json(url, timeout=18, cookie=""):
headers = {
"User-Agent": UA,
"Referer": REFERER,
"Accept": "application/json, text/plain, /",
}

if cookie:
    headers["Cookie"] = cookie.strip()

req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
except Exception as e:
    raise RuntimeError("网络请求失败：" + str(e))

try:
    data = json.loads(raw)
except Exception:
    raise RuntimeError("B站接口返回的数据无法解析")

if not isinstance(data, dict):
    raise RuntimeError("B站接口返回了无法识别的数据")

return data

=========================================================

输入解析

=========================================================

def normalize_input(text):
text = (text or "").strip()

if not text:
    raise ValueError("请先输入 BV 号、AV 号或视频链接")

# BV
bv = re.search(r"BV[0-9A-Za-z]{10}", text, re.I)

if bv:
    bvid = bv.group(0)

    return "https://www.bilibili.com/video/" + bvid

# AV
av = re.search(
    r"(?i)(?:av\s*|/video/av)(\d+)",
    text
)

if av:
    return "https://www.bilibili.com/video/av" + av.group(1)

# b23.tv
short = re.search(
    r"https?://(?:b23\.tv|bili2233\.cn)/[^\s，。；,.;]+",
    text,
    re.I
)

if short:
    return short.group(0).rstrip("，。；,.;")

# bilibili.com
url = re.search(r"https?://\S+", text)

if url:
    candidate = url.group(0).rstrip("，。；,.;")

    if (
        "bilibili.com" in candidate.lower()
        or "b23.tv" in candidate.lower()
    ):
        return candidate

raise ValueError(
    "没有识别到有效的 BV/AV 号或 B 站链接"
)

def resolve_url(text):
url = normalize_input(text)

if "b23.tv" in url.lower():
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": REFERER,
        }
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=15
        ) as resp:
            final = resp.geturl()

        return final

    except Exception:
        raise RuntimeError(
            "短链接展开失败，请直接输入 BV 号"
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
    r"/video/av(\d+)|(?:^|[^a-zA-Z])av(\d+)",
    url,
    re.I
)

if av:
    aid_str = av.group(1) or av.group(2)

    return {
        "aid": int(aid_str)
    }

raise RuntimeError(
    "链接内找不到 BV/AV 编号"
)

=========================================================

视频信息

=========================================================

def get_video_info(text):
url = resolve_url(text)

ids = _extract_ids(url)

query = urllib.parse.urlencode(ids)

api_url = (
    "https://api.bilibili.com/x/web-interface/view?"
    + query
)

data = _request_json(api_url)

if data.get("code") != 0 or not data.get("data"):
    msg = (
        data.get("message")
        or ("code=" + str(data.get("code")))
    )

    raise RuntimeError(
        "获取视频信息失败：" + msg
    )

d = data["data"]

pages = d.get("pages") or [{}]

page0 = pages[0] if pages else {}

owner = d.get("owner") or {}
stat = d.get("stat") or {}

return {
    "bvid": d.get("bvid", ""),
    "aid": d.get("aid", ""),
    "cid": page0.get("cid", 0),

    "title": d.get(
        "title",
        "未命名视频"
    ),

    "owner": owner.get(
        "name",
        "未知UP主"
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

    "share": stat.get(
        "share",
        0
    ),

    "pubdate": d.get(
        "pubdate",
        0
    ),

    "pages": pages,

    "url": url,
}

=========================================================

画质

=========================================================

def _quality_label(q):
mapping = {
127: "8K",
126: "杜比视界",
125: "HDR",
120: "4K",
116: "1080P高码率",
112: "1080P+",
80: "1080P",
74: "720P60",
64: "720P",
32: "480P",
16: "360P",
}

try:
    q = int(q)
except Exception:
    return "未知画质"

return mapping.get(
    q,
    "画质" + str(q)
)

=========================================================

获取真实可用下载画质

=========================================================

def get_download_options(info, cookie=""):
headers = {
"User-Agent": UA,
"Referer": REFERER,
}

if cookie and cookie.strip():
    headers["Cookie"] = cookie.strip()

def fetch(qn):
    params = {
        "qn": qn,
        "fnval": 0,
        "fnver": 0,
        "fourk": 1,
    }

    if info.get("bvid"):
        params["bvid"] = info["bvid"]
    else:
        params["avid"] = info["aid"]

    params["cid"] = info["cid"]

    url = (
        "https://api.bilibili.com/x/player/playurl?"
        + urllib.parse.urlencode(params)
    )

    req = urllib.request.Request(
        url,
        headers=headers
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=22
        ) as response:

            raw = response.read().decode(
                "utf-8",
                "replace"
            )

        result = json.loads(raw)

        return result, None

    except Exception as e:
        return None, str(e)

# 先获取服务器实际允许的画质
base, err = fetch(0)

if err:
    raise RuntimeError(
        "获取播放地址失败：" + err
    )

if not base or base.get("code") != 0:
    message = (
        (base or {}).get("message")
        or "未知错误"
    )

    raise RuntimeError(
        "获取播放地址失败：" + message
    )

base_data = base.get("data") or {}

accept_q = (
    base_data.get("accept_quality")
    or []
)

accept_desc = (
    base_data.get("accept_description")
    or []
)

if not accept_q:
    raise RuntimeError(
        "B站没有返回可用画质"
    )

label_dict = {}

for index, qn in enumerate(accept_q):

    try:
        qn_int = int(qn)
    except Exception:
        continue

    if index < len(accept_desc):
        desc = accept_desc[index]

        if desc:
            label_dict[qn_int] = str(desc)

    if qn_int not in label_dict:
        label_dict[qn_int] = _quality_label(
            qn_int
        )

output = []

# 只请求服务器真正提供的画质
quality_list = sorted(
    set(int(x) for x in accept_q),
    reverse=True
)

for qn in quality_list:

    result, error = fetch(qn)

    if error:
        continue

    if not result:
        continue

    if result.get("code") != 0:
        continue

    data = result.get("data") or {}

    durl_list = data.get("durl") or []

    if not durl_list:
        continue

    # 某些接口可能返回多个分段
    first = durl_list[0] or {}

    download_url = first.get("url")

    if not download_url:
        continue

    try:
        size = int(
            first.get("size") or 0
        )
    except Exception:
        size = 0

    output.append({
        "quality": qn,
        "label": label_dict.get(
            qn,
            _quality_label(qn)
        ),
        "url": download_url,
        "size": size,
    })

if not output:
    raise RuntimeError(
        "该视频没有可用的直连 MP4。"
        "部分视频需要登录 Cookie，"
        "DASH 音视频分离暂不支持。"
    )

return output

=========================================================

B站关键词搜索

=========================================================

def bilibili_search(keyword):
keyword = (keyword or "").strip()

if not keyword:
    return []

params = {
    "keyword": keyword,
    "page": 1,
    "page_size": 20,
    "search_type": "video",
}

url = (
    "https://api.bilibili.com/x/web-interface/search/type?"
    + urllib.parse.urlencode(params)
)

data = _request_json(
    url,
    timeout=20
)

if data.get("code") != 0:
    message = (
        data.get("message")
        or "搜索失败"
    )

    raise RuntimeError(
        "B站搜索失败：" + message
    )

result = data.get("data") or {}

raw_list = result.get("result") or []

output = []

for item in raw_list:

    if not isinstance(item, dict):
        continue

    bvid = item.get("bvid") or ""

    if not bvid:
        # 某些搜索结果可能只有 aid
        aid = item.get("aid")

        if aid:
            bvid = ""

    if not bvid:
        continue

    title = item.get("title") or "未命名视频"

    # 搜索接口的标题可能带 HTML 标签
    title = re.sub(
        r"<[^>]+>",
        "",
        str(title)
    )

    title = (
        title.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )

    author = (
        item.get("author")
        or item.get("up_name")
        or "未知UP主"
    )

    duration = (
        item.get("duration")
        or "--:--"
    )

    pubdate = item.get(
        "pubdate",
        ""
    )

    if pubdate:
        try:
            # 搜索接口通常给 Unix 时间戳
            if str(pubdate).isdigit():
                pubdate = (
                    __import__("datetime")
                    .datetime.datetime
                    .fromtimestamp(
                        int(pubdate)
                    )
                    .strftime("%Y-%m-%d")
                )
        except Exception:
            pass

    # 搜索接口封面可能是 // 开头
    cover = (
        item.get("pic")
        or item.get("cover")
        or ""
    )

    if cover.startswith("//"):
        cover = "https:" + cover

    output.append({
        "bvid": bvid,
        "aid": item.get("aid", ""),
        "title": title,
        "author": str(author),
        "duration": str(duration),
        "pubdate": str(pubdate),
        "cover": cover,
        "play": item.get("play", 0),
        "view": item.get("view", 0),
        "danmaku": item.get("video_review", 0),
        "description": re.sub(
            r"<[^>]+>",
            "",
            str(item.get("description") or "")
        ),
    })

return output
