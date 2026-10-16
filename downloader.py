# -*- coding: utf-8 -*-
"""BiliPink downloader.
Pure urllib implementation.
No yt-dlp dependency.
"""

import os
import re
import urllib.request


UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


def safe_filename(name):
    name = str(
        name or "BiliPink Video"
    )

    name = re.sub(
        r'[\\/:*?"<>|\x00-\x1F]',
        "_",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip(" .")

    if len(name) > 96:
        name = name[:96]

    return name or "BiliPink Video"


def _headers():
    return {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "*/*",
    }


def download_stream(
    url,
    output_path,
    progress=None,
    cancel_check=None
):
    out_dir = os.path.dirname(output_path)

    if out_dir:
        os.makedirs(
            out_dir,
            exist_ok=True
        )

    temp = output_path + ".part"

    req = urllib.request.Request(
        url,
        headers=_headers()
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=48
        ) as rsp:

            status = getattr(
                rsp,
                "status",
                200
            )

            if not (
                200 <= status < 300
            ):
                raise RuntimeError(
                    "HTTP {}: Bilibili rejected the request."
                    .format(status)
                )

            content_type = (
                rsp.headers.get(
                    "Content-Type"
                ) or ""
            ).lower()

            if (
                "text/html" in content_type
                or "application/json" in content_type
            ):
                raise RuntimeError(
                    "The returned data is not a video. "
                    "Please parse the video again."
                )

            total = int(
                rsp.headers.get(
                    "Content-Length"
                ) or 0
            )

            done = 0

            with open(
                temp,
                "wb"
            ) as f:

                while True:

                    if (
                        cancel_check
                        and cancel_check()
                    ):
                        raise InterruptedError(
                            "Download cancelled."
                        )

                    chunk = rsp.read(
                        256 * 1024
                    )

                    if not chunk:
                        break

                    f.write(chunk)
                    done += len(chunk)

                    if progress:
                        progress(
                            done,
                            total
                        )

        if done <= 1024:
            raise RuntimeError(
                "Downloaded file is too small. "
                "The link may have expired."
            )

        os.replace(
            temp,
            output_path
        )

        return output_path

    except Exception:

        try:
            if os.path.exists(temp):
                os.remove(temp)
        except Exception:
            pass

        raise


def download_dash(
    video_url,
    audio_url,
    video_path,
    audio_path,
    progress=None,
    cancel_check=None
):
    """Download DASH video and audio separately.

    progress receives:
        done_bytes, total_bytes
    """

    video_done = 0
    video_total = 0

    audio_done = 0
    audio_total = 0

    def video_progress(done, total):
        nonlocal video_done, video_total

        video_done = done
        video_total = total

        _report_progress()

    def audio_progress(done, total):
        nonlocal audio_done, audio_total

        audio_done = done
        audio_total = total

        _report_progress()

    def _report_progress():
        total = video_total + audio_total
        done = video_done + audio_done

        if progress:
            progress(
                done,
                total
            )

    try:

        download_stream(
            video_url,
            video_path,
            progress=video_progress,
            cancel_check=cancel_check
        )

        download_stream(
            audio_url,
            audio_path,
            progress=audio_progress,
            cancel_check=cancel_check
        )

        return {
            "video_path": video_path,
            "audio_path": audio_path
        }

    except Exception:

        for path in (
            video_path,
            audio_path
        ):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        raise


def merge_mp4(
    video_path,
    audio_path,
    output_path
):
    """Merge MP4 video/audio using Android ffmpeg if available.

    This function does not require ffmpeg during normal
    Python import. It searches common Android executable
    locations.
    """

    import subprocess

    ffmpeg_candidates = [
        "/data/data/org.bilipink/files/ffmpeg",
        "/data/data/org.bilipink/files/bin/ffmpeg",
        "/data/data/org.bilipink/cache/ffmpeg",
    ]

    ffmpeg = None

    for candidate in ffmpeg_candidates:
        if os.path.isfile(candidate):
            ffmpeg = candidate
            break

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is not included in this build. "
            "DASH video and audio were downloaded separately."
        )

    out_dir = os.path.dirname(output_path)

    if out_dir:
        os.makedirs(
            out_dir,
            exist_ok=True
        )

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        output_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        error = result.stderr.decode(
            "utf-8",
            "replace"
        )

        raise RuntimeError(
            "FFmpeg merge failed: "
            + error[-1500:]
        )

    return output_path
