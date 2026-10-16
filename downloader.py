# -*- coding: utf-8 -*-
"""BiliPink downloader without FFmpeg."""

import os
import re
import urllib.request


USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 Chrome/125.0.0.0 Mobile Safari/537.36"
)


def install_ffmpeg_from_assets():
    """Compatibility no-op: this downloader uses Android MediaMuxer, not FFmpeg."""
    return False


def safe_filename(name):
    name = str(name or "video").strip()
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    return (name or "video")[:160]


def _headers():
    return {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
    }


def _check_cancel(cancel_check):
    if callable(cancel_check) and cancel_check():
        raise InterruptedError("任务已取消")


def download_stream(
    url,
    output_path,
    progress=None,
    cancel_check=None,
):
    """Download one media stream. No FFmpeg is required."""
    if not url:
        raise ValueError("下载地址为空")

    output_path = os.path.abspath(output_path)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    temp_path = output_path + ".part"
    request = urllib.request.Request(url, headers=_headers())
    downloaded = 0

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status and status >= 400:
                raise RuntimeError(f"下载失败，HTTP {status}")

            total = int(
                response.headers.get("Content-Length", "0") or 0
            )

            with open(temp_path, "wb") as output:
                while True:
                    _check_cancel(cancel_check)

                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break

                    output.write(chunk)
                    downloaded += len(chunk)

                    if callable(progress):
                        try:
                            progress(downloaded, total)
                        except TypeError:
                            percent = (
                                int(downloaded * 100 / total)
                                if total > 0 else 0
                            )
                            progress(percent)

        _check_cancel(cancel_check)

        if downloaded <= 0:
            raise RuntimeError("下载结果为空")

        os.replace(temp_path, output_path)
        return output_path

    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise


def download_dash(
    video_url,
    audio_url,
    video_path,
    audio_path,
    progress=None,
    cancel_check=None,
):
    """Download separate DASH video and audio streams."""
    video_result = download_stream(
        video_url,
        video_path,
        progress=progress,
        cancel_check=cancel_check,
    )

    _check_cancel(cancel_check)

    audio_result = download_stream(
        audio_url,
        audio_path,
        progress=progress,
        cancel_check=cancel_check,
    )

    return video_result, audio_result


def merge_mp4(
    video_path,
    audio_path,
    output_path,
    cancel_check=None,
):
    """Merge streams using the Android MediaMerger Java class."""
    _check_cancel(cancel_check)

    video_path = os.path.abspath(video_path)
    audio_path = os.path.abspath(audio_path)
    output_path = os.path.abspath(output_path)

    if not os.path.isfile(video_path):
        raise FileNotFoundError("找不到视频流文件：" + video_path)

    if not os.path.isfile(audio_path):
        raise FileNotFoundError("找不到音频流文件：" + audio_path)

    if os.path.getsize(video_path) <= 0:
        raise RuntimeError("视频流文件为空")

    if os.path.getsize(audio_path) <= 0:
        raise RuntimeError("音频流文件为空")

    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        from jnius import autoclass

        PythonActivity = autoclass(
            "org.kivy.android.PythonActivity"
        )
        MediaMerger = autoclass("org.bilipink.MediaMerger")

        activity = PythonActivity.mActivity
        context = activity.getApplicationContext()

        _check_cancel(cancel_check)

        result = MediaMerger.merge(
            context,
            video_path,
            audio_path,
            output_path,
        )

        if not result:
            raise RuntimeError(
                "Android 原生合并失败。输入媒体格式可能不受支持。"
            )

        if not os.path.isfile(output_path):
            raise RuntimeError("合并未生成输出文件")

        if os.path.getsize(output_path) <= 0:
            raise RuntimeError("合并结果为空文件")

        _check_cancel(cancel_check)
        return output_path

    except Exception:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass
        raise
