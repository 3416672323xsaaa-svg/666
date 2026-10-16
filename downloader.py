# -*- coding: utf-8 -*-
"""BiliPink downloader with Android ARM64 FFmpeg support."""

import os
import re
import shutil
import subprocess
import urllib.request


USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 Chrome/125.0.0.0 Mobile Safari/537.36"
)


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


def get_ffmpeg_path():
    """Find FFmpeg in the app-private directory."""
    candidates = []

    try:
        from kivy.app import App
        app = App.get_running_app()
        if app:
            candidates.extend([
                os.path.join(app.user_data_dir, "ffmpeg"),
                os.path.join(app.user_data_dir, "bin", "ffmpeg"),
                os.path.join(app.directory, "ffmpeg"),
            ])
    except Exception:
        pass

    candidates.extend([
        "/data/data/org.bilipink/files/ffmpeg",
        "/data/data/org.bilipink/files/bin/ffmpeg",
        "/data/data/org.bilipink/cache/ffmpeg",
    ])

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # This only works when FFmpeg is available on PATH.
    return shutil.which("ffmpeg")


def install_ffmpeg_from_assets():
    """
    Extract assets/ffmpeg from the APK into the app-private directory.
    Must be called from the app after Kivy has initialized.
    """
    from kivy.app import App

    app = App.get_running_app()
    if app is None:
        raise RuntimeError("应用尚未启动，无法安装 FFmpeg")

    target = os.path.join(app.user_data_dir, "ffmpeg")
    os.makedirs(app.user_data_dir, exist_ok=True)

    if os.path.isfile(target) and os.access(target, os.X_OK):
        return target

    if not hasattr(app, "user_data_dir"):
        raise RuntimeError("无法获取应用私有目录")

    try:
        from jnius import autoclass

        PythonActivity = autoclass(
            "org.kivy.android.PythonActivity"
        )
        activity = PythonActivity.mActivity
        stream = activity.getAssets().open("ffmpeg")

        temp = target + ".tmp"
        try:
            with open(temp, "wb") as output:
                buffer = bytearray(8192)
                while True:
                    count = stream.read(buffer)
                    if count is None or count <= 0:
                        break
                    output.write(buffer[:count])
        finally:
            stream.close()

        os.replace(temp, target)
        os.chmod(target, 0o700)

        # Validate that the executable can run.
        result = subprocess.run(
            [target, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg 启动失败："
                + (result.stdout or "")[-1000:]
            )

        return target

    except Exception as exc:
        try:
            if os.path.exists(target + ".tmp"):
                os.remove(target + ".tmp")
        except Exception:
            pass

        raise RuntimeError(
            "无法从 APK 资源安装 FFmpeg。"
            "请确认 assets/ffmpeg 已打包且适用于 Android ARM64。"
            f"详细信息：{exc}"
        ) from exc


def download_stream(
    url,
    output_path,
    progress=None,
    cancel_check=None,
):
    """Download a single media stream to a .part file."""
    if not url:
        raise ValueError("下载地址为空")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    temp_path = output_path + ".part"

    request = urllib.request.Request(
        url,
        headers=_headers(),
    )

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
                    if callable(cancel_check) and cancel_check():
                        raise InterruptedError("下载已取消")

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

        if downloaded <= 0:
            raise RuntimeError("下载结果为空")

        os.replace(temp_path, output_path)
        return output_path

    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
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
    """Download DASH video and audio streams separately."""
    download_stream(
        video_url,
        video_path,
        progress=progress,
        cancel_check=cancel_check,
    )

    download_stream(
        audio_url,
        audio_path,
        progress=progress,
        cancel_check=cancel_check,
    )

    return video_path, audio_path


def merge_mp4(video_path, audio_path, output_path):
    """Merge video and audio using FFmpeg stream copy."""
    if not os.path.isfile(video_path):
        raise FileNotFoundError("找不到视频流文件：" + video_path)

    if not os.path.isfile(audio_path):
        raise FileNotFoundError("找不到音频流文件：" + audio_path)

    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError(
            "没有找到 FFmpeg。请先在应用启动时调用 "
            "install_ffmpeg_from_assets()。"
        )

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    temp_output = output_path + ".part.mp4"

    command = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c", "copy",
        "-movflags", "+faststart",
        temp_output,
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1800,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg 合并失败：\n"
                + (result.stdout or "")[-3000:]
            )

        if not os.path.isfile(temp_output):
            raise RuntimeError("FFmpeg 没有生成输出文件")

        if os.path.getsize(temp_output) <= 0:
            raise RuntimeError("合并结果为空文件")

        os.replace(temp_output, output_path)
        return output_path

    except Exception:
        try:
            if os.path.exists(temp_output):
                os.remove(temp_output)
        except Exception:
            pass
        raise
