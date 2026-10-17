# -*- coding: utf-8 -*-
"""BiliPink - Android Bilibili downloader.

This version is designed for Kivy 2.2.x and the existing bili_api.py / downloader.py.
It intentionally avoids KivyMD-only widgets and modern Image.fit_mode so that it
can run on the current Buildozer configuration.
"""

import os
import re
import sys
import json
import time
import shutil
import threading
import traceback
import urllib.request
from datetime import datetime

# Make HTTPS certificate handling explicit on Android. A missing certifi package
# must not prevent the UI from starting; bili_api.py also has its own fallback.
try:
    import certifi
    _cert_path = certifi.where()
    if _cert_path and os.path.isfile(_cert_path):
        os.environ.setdefault("SSL_CERT_FILE", _cert_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _cert_path)
except Exception:
    pass

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line

from bili_api import get_video_info, get_download_options, bilibili_search
from downloader import (
    download_stream,
    download_dash,
    merge_mp4,
    safe_filename,
    install_ffmpeg_from_assets,
)

PINK = (0.91, 0.39, 0.57, 1)
PINK_DARK = (0.79, 0.25, 0.46, 1)
PINK_LIGHT = (1.0, 0.91, 0.95, 1)
WHITE = (1, 1, 1, 1)
BG = (0.985, 0.980, 0.985, 1)
TEXT = (0.22, 0.21, 0.23, 1)
MUTED = (0.52, 0.51, 0.53, 1)
GREEN = (0.22, 0.58, 0.34, 1)
RED = (0.78, 0.20, 0.26, 1)
BORDER = (0.91, 0.87, 0.90, 1)
FONT = "Roboto"
_FONT_LOADED = False
UA = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


def fmt_num(value):
    try:
        n = int(value or 0)
        if n >= 100000000:
            return f"{n / 100000000:.1f}亿"
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(n)
    except Exception:
        return str(value or 0)


def fmt_time(value):
    try:
        n = max(0, int(value or 0))
        if n >= 3600:
            return f"{n // 3600:02d}:{n % 3600 // 60:02d}:{n % 60:02d}"
        return f"{n // 60:02d}:{n % 60:02d}"
    except Exception:
        return "--:--"


def human_size(value):
    try:
        n = max(0.0, float(value or 0))
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                return f"{n:.1f} {unit}"
            n /= 1024
    except Exception:
        pass
    return "未知大小"


class Surface(BoxLayout):
    """Rounded white/pink card painted with Kivy canvas primitives."""

    def __init__(self, bg=WHITE, radius=None, **kwargs):
        super().__init__(**kwargs)
        self._bg = bg
        self._radius = radius if radius is not None else dp(16)
        with self.canvas.before:
            Color(0, 0, 0, 0.045)
            self.shadow = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
            Color(*self._bg)
            self.rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self.shadow.pos = (self.x, self.y - dp(2))
        self.shadow.size = self.size
        self.rect.pos = self.pos
        self.rect.size = self.size


class BiliPinkApp(App):
    title = "BiliPink"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.busy = False
        self.current_info = None
        self.current_options = []
        self.tasks = []
        self.history = []
        self.search_result_list = []
        self.filter = "全部"
        self.page_name = "home"
        self.cancel_flags = {}
        self._history_lock = threading.Lock()
        self._last_error = ""

    # ---------------------------- start / crash handling ---------------------
    def build(self):
        try:
            return self._build_ui()
        except Exception:
            self._write_crash_log("build() failed")
            # Keep the process alive and show the error instead of silently closing.
            root = BoxLayout(
                orientation="vertical",
                padding=dp(16),
                spacing=dp(10),
            )
            root.add_widget(Label(
                text="BiliPink 启动遇到错误\n\n请截图此页面并反馈。\n\n"
                     + self._last_error[-1800:],
                color=TEXT,
                halign="left",
                valign="middle",
            ))
            return root

    def _build_ui(self):
        Window.clearcolor = BG
        self._load_history()

        # This helper is currently a no-op in downloader.py, but retaining the
        # guarded background call keeps compatibility with older project copies.
        if platform == "android":
            try:
                threading.Thread(
                    target=install_ffmpeg_from_assets,
                    daemon=True,
                ).start()
            except Exception:
                pass

        self.root_layout = BoxLayout(
            orientation="vertical",
            spacing=0,
        )
        self.body = BoxLayout(orientation="vertical")
        self.root_layout.add_widget(self.body)
        self.nav = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(62),
            padding=[dp(30), dp(4), dp(30), dp(4)],
            spacing=dp(48),
        )
        self.root_layout.add_widget(self.nav)
        Clock.schedule_once(self._load_cjk_font_safe, 0.25)
        self.show_home()
        return self.root_layout

    def _write_crash_log(self, label="Uncaught exception"):
        try:
            self._last_error = traceback.format_exc()
            base = getattr(self, "user_data_dir", None) or os.path.join(
                os.path.expanduser("~"), ".bilipink"
            )
            os.makedirs(base, exist_ok=True)
            with open(
                os.path.join(base, "crash.log"),
                "a",
                encoding="utf-8",
            ) as f:
                f.write(
                    "\n\n===== " + label + " "
                    + datetime.now().isoformat() + " =====\n"
                )
                f.write(self._last_error)
        except Exception:
            pass

    def on_exception(self, exception):
        try:
            self._last_error = "".join(traceback.format_exception(
                type(exception),
                exception,
                exception.__traceback__,
            ))
            base = getattr(self, "user_data_dir", None) or os.path.join(
                os.path.expanduser("~"), ".bilipink"
            )
            os.makedirs(base, exist_ok=True)
            with open(
                os.path.join(base, "crash.log"),
                "a",
                encoding="utf-8",
            ) as f:
                f.write(
                    "\n\n===== Kivy callback error "
                    + datetime.now().isoformat() + " =====\n"
                )
                f.write(self._last_error)
            if getattr(self, "root_layout", None):
                Clock.schedule_once(
                    lambda _dt: self._popup(
                        "运行错误",
                        "出现了一个运行错误，详细信息已保存到应用目录 "
                        "crash.log。\n\n" + str(exception),
                    ),
                    0,
                )
        except Exception:
            pass
        return True

    # ---------------------------- font / assets -----------------------------
    def _extract_asset_to_file(self, asset_path, dest_path):
        if platform != "android":
            local = os.path.abspath(asset_path)
            return local if os.path.isfile(local) else None
        try:
            from jnius import autoclass
            activity = autoclass(
                "org.kivy.android.PythonActivity"
            ).mActivity
            stream = activity.getAssets().open(asset_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            try:
                with open(dest_path, "wb") as output:
                    while True:
                        byte_value = stream.read()
                        if int(byte_value) < 0:
                            break
                        output.write(bytes([int(byte_value) & 255]))
            finally:
                stream.close()
            return dest_path if os.path.isfile(dest_path) else None
        except Exception:
            return None

    def _load_cjk_font_safe(self, _dt):
        global FONT, _FONT_LOADED
        if _FONT_LOADED:
            return
        try:
            font_path = os.path.join(
                self.user_data_dir,
                "NotoSansSC-Regular.otf",
            )
            if not os.path.isfile(font_path):
                self._extract_asset_to_file(
                    "fonts/NotoSansSC-Regular.otf",
                    font_path,
                )
            if os.path.isfile(font_path):
                LabelBase.register(
                    name="BiliCJK",
                    fn_regular=font_path,
                    fn_bold=font_path,
                    fn_italic=font_path,
                    fn_bolditalic=font_path,
                )
                FONT = "BiliCJK"
            else:
                FONT = "Roboto"
        except Exception:
            FONT = "Roboto"
        _FONT_LOADED = True
        try:
            if self.page_name == "home":
                self.show_home()
            elif self.page_name == "mine":
                self.show_mine()
            elif self.page_name == "details":
                self.show_video_options()
        except Exception:
            self._write_crash_log("font refresh failed")

    def _load_avatar(self):
        try:
            path = os.path.join(
                self.user_data_dir,
                "avatar-reference.jpg",
            )
            if os.path.isfile(path):
                return path
            return self._extract_asset_to_file(
                "fonts/avatar-reference.jpg",
                path,
            )
        except Exception:
            return None

    # ---------------------------- common widgets ----------------------------
    def _label(
        self,
        text,
        size=14,
        color=TEXT,
        bold=False,
        halign="left",
        height=None,
    ):
        label = Label(
            text=str(text),
            font_name=FONT,
            font_size=dp(size),
            color=color,
            bold=bold,
            halign=halign,
            valign="middle",
            size_hint_y=None,
            height=dp(height if height is not None else max(25, size * 1.8)),
        )
        label.bind(
            size=lambda obj, *_: setattr(
                obj, "text_size", (obj.width, None)
            )
        )
        return label

    def _btn(
        self,
        text,
        callback,
        color=WHITE,
        fg=TEXT,
        height=None,
        bold=False,
    ):
        button = Button(
            text=str(text),
            font_name=FONT,
            font_size=dp(14),
            bold=bold,
            background_normal="",
            background_down="",
            background_color=color,
            color=fg,
            size_hint_y=None,
            height=height if height is not None else dp(44),
        )
        button.bind(
            on_release=lambda *_: self._safe_callback(callback)
        )
        return button

    def _safe_callback(self, callback):
        try:
            callback()
        except Exception as exc:
            self._write_crash_log("button callback failed")
            self._popup("操作失败", str(exc))

    def _scroll(self):
        self.body.clear_widgets()
        self.scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            scroll_type=["bars", "content"],
        )
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(12),
            padding=[dp(16), dp(10), dp(16), dp(16)],
        )
        self.content.bind(
            minimum_height=self.content.setter("height")
        )
        self.scroll.add_widget(self.content)
        self.body.add_widget(self.scroll)

    def _nav(self):
        self.nav.clear_widgets()
        for key, caption, symbol in (
            ("home", "主页", "⌂"),
            ("mine", "已下载", "♡"),
        ):
            active = self.page_name == key
            color = PINK if active else MUTED
            cell = BoxLayout(
                orientation="vertical",
                spacing=0,
            )
            button = Button(
                text=symbol,
                font_name=FONT,
                font_size=dp(23),
                color=color,
                background_normal="",
                background_color=(0, 0, 0, 0),
            )
            label = Label(
                text=caption,
                font_name=FONT,
                font_size=dp(12),
                color=color,
            )

            def navigate(_instance, selected=key):
                if selected == "home":
                    self.show_home()
                else:
                    self.show_mine()

            button.bind(on_release=navigate)
            label.bind(
                on_touch_down=lambda obj, touch, selected=key:
                self._nav_touch(obj, touch, selected)
            )
            cell.add_widget(button)
            cell.add_widget(label)
            self.nav.add_widget(cell)

    def _nav_touch(self, obj, touch, page):
        if obj.collide_point(*touch.pos):
            self.show_home() if page == "home" else self.show_mine()
            return True
        return False

    def _popup(self, title, message):
        try:
            layout = BoxLayout(
                orientation="vertical",
                spacing=dp(12),
                padding=dp(14),
            )
            scroll = ScrollView(do_scroll_x=False)
            label = Label(
                text=str(message),
                font_name=FONT,
                font_size=dp(13),
                color=TEXT,
                halign="left",
                valign="top",
                size_hint_y=None,
            )
            label.bind(
                width=lambda obj, width:
                setattr(obj, "text_size", (width, None))
            )
            label.bind(
                texture_size=lambda obj, size:
                setattr(obj, "height", size[1] + dp(8))
            )
            scroll.add_widget(label)
            layout.add_widget(scroll)
            popup = Popup(
                title=str(title),
                content=layout,
                size_hint=(0.90, 0.68),
            )
            layout.add_widget(
                self._btn(
                    "关闭",
                    popup.dismiss,
                    PINK,
                    WHITE,
                    dp(42),
                    True,
                )
            )
            popup.open()
        except Exception:
            print("[BiliPink popup]", title, message)

    # ---------------------------- main page ---------------------------------
    def show_home(self):
        self.page_name = "home"
        self._scroll()
        self._nav()

        header = BoxLayout(
            size_hint_y=None,
            height=dp(60),
            spacing=dp(10),
        )
        avatar_path = self._load_avatar()
        if avatar_path and os.path.isfile(avatar_path):
            # allow_stretch/keep_ratio work on Kivy 2.2.x; fit_mode is avoided
            # because it has caused startup errors on older packaged Kivy builds.
            avatar = Image(
                source=avatar_path,
                allow_stretch=True,
                keep_ratio=True,
                size_hint_x=None,
                width=dp(48),
            )
        else:
            avatar = Label(
                text="♡",
                font_name=FONT,
                font_size=dp(30),
                color=PINK,
                size_hint_x=None,
                width=dp(48),
            )
        header.add_widget(avatar)

        search = BoxLayout(
            size_hint_y=None,
            height=dp(46),
            padding=[dp(8), dp(2)],
            spacing=dp(5),
        )
        with search.canvas.before:
            Color(*WHITE)
            search.bg = RoundedRectangle(
                pos=search.pos,
                size=search.size,
                radius=[dp(22)],
            )
            Color(*BORDER)
            search.border = Line(
                rounded_rectangle=(
                    search.x,
                    search.y,
                    search.width,
                    search.height,
                    dp(22),
                ),
                width=1,
            )

        def update_search_bg(widget, *_):
            search.bg.pos = widget.pos
            search.bg.size = widget.size
            search.border.rounded_rectangle = (
                widget.x,
                widget.y,
                widget.width,
                widget.height,
                dp(22),
            )

        search.bind(pos=update_search_bg, size=update_search_bg)

        self.search_input = TextInput(
            hint_text="输入 BV / AV / B站链接 / 关键词",
            font_name=FONT,
            font_size=dp(14),
            multiline=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            cursor_color=PINK,
            padding=[dp(4), dp(10)],
        )
        self.search_input.bind(
            on_text_validate=lambda *_: self.do_search_or_parse()
        )
        search.add_widget(self.search_input)
        search.add_widget(
            self._btn(
                "搜索",
                self.do_search_or_parse,
                PINK,
                WHITE,
                dp(38),
                True,
            )
        )
        header.add_widget(search)
        self.content.add_widget(header)

        filter_row = BoxLayout(
            size_hint_y=None,
            height=dp(40),
            spacing=dp(5),
        )
        for name in ("全部", "已完成", "进行中", "已失败"):
            selected = self.filter == name
            filter_row.add_widget(
                self._btn(
                    name,
                    lambda value=name: self.set_filter(value),
                    PINK if selected else WHITE,
                    WHITE if selected else MUTED,
                    dp(36),
                    selected,
                )
            )
        self.content.add_widget(filter_row)

        if self.busy:
            self.content.add_widget(
                self._label(
                    "正在处理，请稍候……",
                    12,
                    MUTED,
                    height=dp(30),
                )
            )

        if self.search_result_list:
            self.content.add_widget(
                self._label(
                    "搜索结果",
                    17,
                    PINK,
                    True,
                    height=dp(34),
                )
            )
            for item in self.search_result_list:
                self.content.add_widget(self._search_result_card(item))

        visible = []
        active_statuses = (
            "解析中",
            "等待下载",
            "下载中",
            "合并中",
        )
        for task in self.tasks:
            status = task.get("status", "")
            if self.filter == "全部":
                visible.append(task)
            elif self.filter == "已完成" and status == "已完成":
                visible.append(task)
            elif self.filter == "进行中" and status in active_statuses:
                visible.append(task)
            elif self.filter == "已失败" and status == "已失败":
                visible.append(task)

        if self.filter in ("全部", "已完成"):
            for record in self.history:
                if not any(
                    t.get("id") == record.get("id")
                    for t in visible
                ):
                    visible.append(dict(record, status="已完成"))

        visible.sort(
            key=lambda item: item.get(
                "created",
                item.get("time", ""),
            ),
            reverse=True,
        )

        if not visible and not self.search_result_list:
            self.content.add_widget(
                self._label(
                    "BiliPink · 粉色的 B 站下载助手\n"
                    "输入 BV / AV / 链接解析视频，或输入关键词搜索。",
                    13,
                    MUTED,
                    False,
                    "center",
                    dp(94),
                )
            )

        for task in visible:
            self.content.add_widget(self._task_card(task))

    def set_filter(self, value):
        self.filter = value
        self.show_home()

    # ---------------------------- search ------------------------------------
    def do_search_or_parse(self):
        text = (
            (getattr(self, "search_input", None).text or "").strip()
            if getattr(self, "search_input", None)
            else ""
        )
        if not text:
            self._popup(
                "提示",
                "请先输入 BV 号、AV 号、B站链接或关键词。",
            )
            return

        # Prevent multiple searches or parses from running in parallel.
        has_video_id = bool(
            re.search(
                r"(?i)BV[0-9A-Za-z]{10}|(?:^|\W)av\s*\d+",
                text,
            )
        )
        has_link = bool(
            re.search(
                r"(?i)(bilibili\.com|b23\.tv|bili2233\.cn)",
                text,
            )
        )
        if has_video_id or has_link:
            self.search_result_list = []
            self.parse_video()
            return

        if self.busy:
            self._popup(
                "请稍候",
                "当前已有搜索或解析任务正在处理。",
            )
            return

        self.busy = True
        self.show_home()
        threading.Thread(
            target=self._search_worker,
            args=(text,),
            daemon=True,
        ).start()

    def _search_worker(self, keyword):
        try:
            result = bilibili_search(keyword)
            error = ""
        except Exception as exc:
            result, error = [], str(exc)
        Clock.schedule_once(
            lambda _dt: self._search_done(result, error),
            0,
        )

    def _search_done(self, result, error=""):
        self.busy = False
        self.search_result_list = result or []
        self.show_home()
        if error:
            self._popup("搜索失败", error)

    def _search_result_card(self, item):
        card = Surface(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(5),
        )
        card.bind(minimum_height=card.setter("height"))
        card.add_widget(
            self._label(
                item.get("title", "未命名视频"),
                14,
                PINK,
                True,
                height=dp(42),
            )
        )
        card.add_widget(
            self._label(
                "UP主：" + str(item.get("author", "未知")),
                12,
                MUTED,
                height=dp(24),
            )
        )
        duration = item.get("duration", "")
        if duration:
            card.add_widget(
                self._label(
                    "时长：" + str(duration),
                    11,
                    MUTED,
                    height=dp(22),
                )
            )
        bvid = item.get("bvid", "")
        card.add_widget(
            self._btn(
                "解析这个视频",
                lambda value=bvid: self.parse_by_bvid(value),
                PINK,
                WHITE,
                dp(38),
                True,
            )
        )
        return card

    def parse_by_bvid(self, bvid):
        if not bvid:
            self._popup("提示", "搜索结果没有提供 BV 号。")
            return
        self.search_input.text = bvid
        self.search_result_list = []
        self.parse_video()

    # ---------------------------- parse -------------------------------------
    def _find_task(self, task_id):
        return next(
            (task for task in self.tasks if task.get("id") == task_id),
            None,
        )

    def parse_video(self):
        if self.busy:
            self._popup("请稍候", "当前已有解析或搜索任务。")
            return

        raw = (
            (getattr(self, "search_input", None).text or "").strip()
            if getattr(self, "search_input", None)
            else ""
        )
        if not raw:
            self._popup("提示", "请先输入视频链接或 BV / AV 号。")
            return

        self.busy = True
        task_id = str(time.time_ns())
        task = {
            "id": task_id,
            "title": "正在解析视频……",
            "status": "解析中",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "percent": 0,
            "error": "",
            "path": "",
        }
        self.tasks.insert(0, task)
        self.show_home()

        threading.Thread(
            target=self._parse_worker,
            args=(raw, task_id),
            daemon=True,
        ).start()

    def _parse_worker(self, raw, task_id):
        try:
            info = get_video_info(raw)
            options = get_download_options(info, "")
            cover_path = ""
            cover_url = (
                info.get("cover")
                or info.get("thumbnail")
                or info.get("pic")
                or ""
            )

            if cover_url:
                try:
                    cover_dir = os.path.join(self.user_data_dir, "covers")
                    os.makedirs(cover_dir, exist_ok=True)
                    cover_path = os.path.join(
                        cover_dir,
                        safe_filename(info.get("bvid", "video")) + ".jpg",
                    )

                    if not os.path.isfile(cover_path):
                        req = urllib.request.Request(
                            cover_url,
                            headers={
                                "User-Agent": UA,
                                "Referer": "https://www.bilibili.com/",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=20) as response:
                            data = response.read()

                        if data:
                            with open(cover_path, "wb") as f:
                                f.write(data)
                except Exception:
                    cover_path = ""

            Clock.schedule_once(
                lambda _dt: self._parsed(
                    task_id,
                    info,
                    options,
                    cover_path,
                ),
                0,
            )

        except Exception as exc:
            message = str(exc)
            Clock.schedule_once(
                lambda _dt: self._parse_error(task_id, message),
                0,
            )

    def _parsed(self, task_id, info, options, cover_path):
        self.busy = False
        self.current_info = info or {}
        self.current_options = options or []

        task = self._find_task(task_id)
        if task:
            task.update({
                "title": self.current_info.get("title", "未命名视频"),
                "status": "等待下载",
                "cover_path": cover_path or "",
                "bvid": self.current_info.get("bvid", ""),
                "percent": 0,
                "error": "",
            })

        self.show_video_options()

    def _parse_error(self, task_id, message):
        self.busy = False
        task = self._find_task(task_id)
        if task:
            task["status"] = "已失败"
            task["error"] = str(message)

        self.show_home()
        self._popup("解析失败", message)

    # ---------------------------- video information / quality ---------------
    def show_video_options(self):
        self.page_name = "details"
        info = self.current_info or {}
        options = self.current_options or []

        self._scroll()
        self._nav()
        self.content.add_widget(
            self._label("视频详情", 22, PINK, True, height=dp(42))
        )

        cover_path = self._cover_for_info(info)
        if cover_path and os.path.isfile(cover_path):
            cover_wrap = BoxLayout(
                size_hint_y=None,
                height=dp(170),
                padding=[dp(4), 0],
            )
            cover_wrap.add_widget(
                Image(
                    source=cover_path,
                    allow_stretch=True,
                    keep_ratio=True,
                )
            )
            self.content.add_widget(cover_wrap)

        self.content.add_widget(
            self._label(
                info.get("title", "未命名视频"),
                17,
                TEXT,
                True,
                height=dp(58),
            )
        )

        owner = info.get("owner", {})
        if isinstance(owner, dict):
            author = owner.get("name", info.get("author", "未知UP主"))
        else:
            author = str(owner or info.get("author", "未知UP主"))

        details = [
            ("BV号", info.get("bvid", "未知")),
            ("AV号", info.get("aid", "未知")),
            ("UP主", author),
            ("UID", info.get("mid", "未知")),
            ("分P数量", len(info.get("pages") or []) or 1),
            ("时长", fmt_time(info.get("duration", 0))),
            ("播放", fmt_num(info.get("view", 0))),
            ("弹幕", fmt_num(info.get("danmaku", 0))),
            ("点赞", fmt_num(info.get("like", 0))),
            ("投币", fmt_num(info.get("coin", 0))),
            ("收藏", fmt_num(info.get("favorite", 0))),
            ("评论", fmt_num(info.get("reply", 0))),
        ]

        card = Surface(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(3),
        )
        card.bind(minimum_height=card.setter("height"))

        for key, value in details:
            card.add_widget(
                self._label(
                    f"{key}：{value}",
                    12,
                    TEXT,
                    height=dp(24),
                )
            )

        self.content.add_widget(card)

        description = info.get("desc", info.get("description", ""))
        if description:
            self.content.add_widget(
                self._label(
                    "视频简介",
                    15,
                    PINK,
                    True,
                    height=dp(32),
                )
            )
            self.content.add_widget(
                self._label(
                    str(description)[:1800],
                    12,
                    MUTED,
                    height=dp(110),
                )
            )

        self.content.add_widget(
            self._label(
                "选择可用画质",
                17,
                PINK,
                True,
                height=dp(38),
            )
        )

        if not options:
            self.content.add_widget(
                self._label(
                    "没有获取到可下载画质，请检查网络、视频权限或 bili_api.py。",
                    13,
                    RED,
                    height=dp(60),
                )
            )

        for option in options:
            self.content.add_widget(
                self._btn(
                    self._option_label(option),
                    lambda selected=option: self._confirm_download(selected),
                    PINK_LIGHT,
                    TEXT,
                    dp(46),
                    True,
                )
            )

        if cover_path and os.path.isfile(cover_path):
            self.content.add_widget(
                self._btn(
                    "导出封面图片",
                    lambda path=cover_path: self._export_file(path),
                    WHITE,
                    PINK,
                    dp(40),
                    True,
                )
            )

        self.content.add_widget(
            self._btn(
                "返回主页",
                self.show_home,
                WHITE,
                PINK,
                dp(42),
                True,
            )
        )

    def _option_label(self, option):
        if not isinstance(option, dict):
            return str(option)

        name = (
            option.get("label")
            or option.get("name")
            or option.get("quality_name")
            or option.get("quality")
            or "可用画质"
        )

        kind = str(option.get("type", "video")).lower()
        kind_text = (
            "DASH 音视频"
            if kind in ("dash", "mp4_dash")
            else ("音频" if "audio" in kind else "视频")
        )

        size = option.get("size", option.get("filesize", 0))
        size_text = ""
        try:
            if float(size or 0) > 0:
                size_text = " · " + human_size(size)
        except (TypeError, ValueError):
            pass

        return f"{name} · {kind_text}{size_text}"

    def _confirm_download(self, option):
        if not isinstance(option, dict):
            self._popup("画质错误", "当前画质数据格式不正确。")
            return

        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(14),
        )
        layout.add_widget(
            self._label(
                self._option_label(option),
                14,
                TEXT,
                True,
                height=dp(48),
            )
        )
        layout.add_widget(
            self._label(
                "确认后开始下载。DASH 画质需要手机支持对应格式以便合并音视频。",
                12,
                MUTED,
                height=dp(48),
            )
        )

        popup = Popup(
            title="确认下载",
            content=layout,
            size_hint=(0.88, 0.40),
        )

        row = BoxLayout(
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )
        row.add_widget(
            self._btn("取消", popup.dismiss, WHITE, TEXT, dp(40))
        )
        row.add_widget(
            self._btn(
                "开始下载",
                lambda: self._begin_download_after_popup(popup, option),
                PINK,
                WHITE,
                dp(40),
                True,
            )
        )
        layout.add_widget(row)
        popup.open()

    def _begin_download_after_popup(self, popup, option):
        popup.dismiss()
        self._start_download(option)

    # ---------------------------- download tasks ----------------------------
    def _start_download(self, option):
        info = self.current_info or {}
        if not info:
            self._popup("无法下载", "请先解析视频。")
            return

        task_id = str(time.time_ns())
        task = {
            "id": task_id,
            "title": info.get("title", "BiliPink_video"),
            "bvid": info.get("bvid", "video"),
            "status": "等待下载",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "percent": 0,
            "cover_path": self._cover_for_info(info),
            "path": "",
            "error": "",
        }

        self.tasks.insert(0, task)
        self.cancel_flags[task_id] = threading.Event()
        self.show_home()

        threading.Thread(
            target=self._download_worker,
            args=(task_id, dict(info), dict(option)),
            daemon=True,
        ).start()

    def _cover_for_info(self, info):
        try:
            path = os.path.join(
                self.user_data_dir,
                "covers",
                safe_filename(info.get("bvid", "video")) + ".jpg",
            )
            return path if os.path.isfile(path) else ""
        except Exception:
            return ""

    def _downloads_dir(self):
        try:
            from android.storage import app_storage_path
            base = app_storage_path()
        except Exception:
            base = self.user_data_dir

        path = os.path.join(base, "downloads")
        os.makedirs(path, exist_ok=True)
        return path

    def _set_task_status(self, task_id, status, percent=None):
        task = self._find_task(task_id)
        if not task:
            return

        task["status"] = status
        if percent is not None:
            task["percent"] = float(percent)

        Clock.schedule_once(
            lambda _dt: self._refresh_if_home(),
            0,
        )

    def _refresh_if_home(self):
        try:
            if self.page_name == "home":
                self.show_home()
            elif self.page_name == "mine":
                self.show_mine()
        except Exception:
            self._write_crash_log("task refresh failed")

    def _set_task_progress(self, task_id, percent):
        task = self._find_task(task_id)
        if task:
            task["percent"] = max(0.0, min(99.0, float(percent)))

    def _download_worker(self, task_id, info, option):
        save_dir = self._downloads_dir()
        title = safe_filename(info.get("title", "BiliPink_video"))
        bvid = safe_filename(info.get("bvid", "video"))

        output_path = os.path.join(
            save_dir,
            f"{title}_{bvid}.mp4",
        )
        if os.path.exists(output_path):
            output_path = os.path.join(
                save_dir,
                f"{title}_{bvid}_{task_id[-6:]}.mp4",
            )

        video_url = (
            option.get("video_url")
            or option.get("url")
            or option.get("durl_url")
        )
        audio_url = option.get("audio_url")
        option_type = str(option.get("type", "")).lower()

        cancel_event = self.cancel_flags.get(task_id)

        def is_cancelled():
            return bool(cancel_event and cancel_event.is_set())

        phase = {"value": "video"}

        def on_progress(downloaded, total):
            if is_cancelled():
                return

            frac = (
                min(1.0, downloaded / total)
                if total and total > 0
                else 0.0
            )

            if phase["value"] == "audio":
                percent = 48 + frac * 48
            else:
                percent = frac * (48 if audio_url else 96)

            Clock.schedule_once(
                lambda _dt, p=percent:
                self._set_task_progress(task_id, p),
                0,
            )

        video_temp = ""
        audio_temp = ""

        try:
            is_dash = option_type in ("dash", "mp4_dash") or bool(audio_url)

            if is_cancelled():
                raise InterruptedError("任务已取消")

            if is_dash:
                if not video_url or not audio_url:
                    raise ValueError(
                        "DASH 画质缺少视频或音频流 URL。"
                        "请检查 bili_api.py 的返回数据。"
                    )

                video_temp = os.path.join(
                    save_dir,
                    f".{task_id}.video.part",
                )
                audio_temp = os.path.join(
                    save_dir,
                    f".{task_id}.audio.part",
                )

                phase["value"] = "video"
                self._set_task_status(task_id, "下载中", 0)

                download_stream(
                    video_url,
                    video_temp,
                    progress=lambda downloaded, total:
                    self._set_task_progress(
                        task_id,
                        (
                            min(1.0, downloaded / total)
                            if total
                            else 0.0
                        ) * 48,
                    ),
                    cancel_check=is_cancelled,
                )

                if is_cancelled():
                    raise InterruptedError("下载已取消")

                phase["value"] = "audio"
                download_stream(
                    audio_url,
                    audio_temp,
                    progress=lambda downloaded, total:
                    self._set_task_progress(
                        task_id,
                        48 + (
                            min(1.0, downloaded / total)
                            if total
                            else 0.0
                        ) * 48,
                    ),
                    cancel_check=is_cancelled,
                )

                if is_cancelled():
                    raise InterruptedError("下载已取消")

                self._set_task_status(task_id, "合并中", 98)
                merge_mp4(
                    video_temp,
                    audio_temp,
                    output_path,
                    cancel_check=is_cancelled,
                )

            else:
                if not video_url:
                    raise ValueError(
                        "该画质没有视频流 URL，请检查 bili_api.py 返回字段。"
                    )

                self._set_task_status(task_id, "下载中", 0)
                download_stream(
                    video_url,
                    output_path,
                    progress=on_progress,
                    cancel_check=is_cancelled,
                )

            if is_cancelled():
                raise InterruptedError("下载已取消")

            if (
                not os.path.isfile(output_path)
                or os.path.getsize(output_path) <= 0
            ):
                raise IOError("下载结束但没有生成有效的输出文件。")

            Clock.schedule_once(
                lambda _dt: self._download_done(task_id, output_path),
                0,
            )

        except Exception as exc:
            message = (
                "任务已取消"
                if isinstance(exc, InterruptedError)
                else str(exc)
            )
            Clock.schedule_once(
                lambda _dt, msg=message:
                self._download_error(task_id, msg),
                0,
            )

        finally:
            for path in (video_temp, audio_temp):
                if path:
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                    except OSError:
                        pass

    def _download_done(self, task_id, path):
        task = self._find_task(task_id)
        if not task:
            return

        task.update({
            "status": "已完成",
            "percent": 100,
            "path": path,
            "error": "",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.cancel_flags.pop(task_id, None)
        self._add_history(task)
        self._refresh_if_home()

        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "未知大小"

        self._popup(
            "下载完成",
            f"{task.get('title', '视频')}\n\n"
            f"保存位置：\n{path}\n\n"
            f"文件大小：{size}\n\n"
            "可在底部“已下载”页面导出到手机 Download。",
        )

    def _download_error(self, task_id, message):
        task = self._find_task(task_id)
        if task:
            task["status"] = "已失败"
            task["error"] = str(message)

        self.cancel_flags.pop(task_id, None)
        self._refresh_if_home()
        self._popup("下载失败", message)

    def cancel_download(self, task_id):
        event = self.cancel_flags.get(task_id)
        if event:
            event.set()
            self._popup(
                "已请求取消",
                "下载线程会在下一次检查时停止。",
            )

    # ---------------------------- task cards --------------------------------
    def _task_card(self, task):
        card = Surface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(108),
            padding=dp(9),
            spacing=dp(10),
        )

        cover_path = task.get("cover_path", "")
        if cover_path and os.path.isfile(cover_path):
            card.add_widget(
                Image(
                    source=cover_path,
                    allow_stretch=True,
                    keep_ratio=True,
                    size_hint_x=None,
                    width=dp(92),
                )
            )
        else:
            placeholder = FloatLayout(
                size_hint_x=None,
                width=dp(92),
            )
            with placeholder.canvas.before:
                Color(*PINK_LIGHT)
                placeholder.rect = RoundedRectangle(
                    pos=placeholder.pos,
                    size=placeholder.size,
                    radius=[dp(10)],
                )

            placeholder.bind(
                pos=lambda obj, *_: setattr(obj.rect, "pos", obj.pos),
                size=lambda obj, *_: setattr(obj.rect, "size", obj.size),
            )
            placeholder.add_widget(
                Label(
                    text="♡",
                    color=PINK,
                    font_size=dp(28),
                )
            )
            card.add_widget(placeholder)

        info = BoxLayout(
            orientation="vertical",
            spacing=dp(2),
        )
        info.add_widget(
            self._label(
                task.get("title", "未命名视频"),
                13,
                PINK,
                True,
                height=dp(36),
            )
        )
        info.add_widget(
            self._label(
                task.get("created", task.get("time", "")),
                10,
                MUTED,
                height=dp(19),
            )
        )

        status = task.get("status", "已完成")
        status_color = (
            GREEN
            if status == "已完成"
            else (RED if status == "已失败" else PINK)
        )
        info.add_widget(
            self._label(
                f"{status}  {float(task.get('percent', 0)):.0f}%",
                11,
                status_color,
                True,
                height=dp(22),
            )
        )

        if status in ("解析中", "等待下载", "下载中", "合并中"):
            info.add_widget(
                ProgressBar(
                    max=100,
                    value=task.get("percent", 0),
                    size_hint_y=None,
                    height=dp(4),
                )
            )

        card.add_widget(info)
        card.bind(
            on_touch_down=lambda widget, touch, current=task:
            self._task_card_touch(widget, touch, current)
        )
        return card

    def _task_card_touch(self, widget, touch, task):
        if widget.collide_point(*touch.pos):
            self._show_task(task)
            return True
        return False

    def _show_task(self, task):
        message = (
            f"标题：{task.get('title', '视频')}\n"
            f"状态：{task.get('status', '未知')}\n"
            f"任务时间：{task.get('created', '')}\n"
            f"进度：{float(task.get('percent', 0)):.0f}%\n"
        )

        path = task.get("path", "")
        if path:
            size = (
                human_size(os.path.getsize(path))
                if os.path.isfile(path)
                else "文件不可访问"
            )
            message += f"\n文件：{path}\n大小：{size}"

        if task.get("error"):
            message += "\n\n错误信息：\n" + str(task["error"])

        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
        )
        scroll = ScrollView(do_scroll_x=False)
        label = self._label(
            message,
            12,
            TEXT,
            height=dp(180),
        )
        label.size_hint_y = None
        label.text_size = (dp(260), None)
        label.bind(
            texture_size=lambda obj, size:
            setattr(obj, "height", size[1] + dp(10))
        )
        scroll.add_widget(label)
        layout.add_widget(scroll)

        popup = Popup(
            title="任务详情",
            content=layout,
            size_hint=(0.90, 0.60),
        )
        row = BoxLayout(
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )

        if task.get("status") in ("下载中", "等待下载"):
            row.add_widget(
                self._btn(
                    "取消任务",
                    lambda: self.cancel_download(task.get("id", "")),
                    RED,
                    WHITE,
                    dp(40),
                )
            )

        row.add_widget(
            self._btn("关闭", popup.dismiss, PINK, WHITE, dp(40))
        )
        layout.add_widget(row)
        popup.open()

    # ---------------------------- history -----------------------------------
    def _history_path(self):
        return os.path.join(self.user_data_dir, "history.json")

    def _load_history(self):
        try:
            with open(self._history_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.history = data if isinstance(data, list) else []
        except Exception:
            self.history = []

    def _save_history(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            temp_path = self._history_path() + ".tmp"

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.history,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            os.replace(temp_path, self._history_path())

        except Exception:
            self._write_crash_log("save history failed")

    def _add_history(self, task):
        record = {
            "id": task.get("id", ""),
            "title": task.get("title", ""),
            "bvid": task.get("bvid", ""),
            "status": "已完成",
            "created": task.get("created", ""),
            "time": task.get("time", ""),
            "percent": 100,
            "path": task.get("path", ""),
            "cover_path": task.get("cover_path", ""),
        }

        with self._history_lock:
            self.history = [
                item for item in self.history
                if item.get("id") != record["id"]
            ]
            self.history.insert(0, record)
            self.history = self.history[:300]
            self._save_history()

    # ---------------------------- downloaded files / export -----------------
    def _list_downloaded_files(self):
        folder = self._downloads_dir()
        results = []

        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if (
                    os.path.isfile(path)
                    and not name.endswith(".part")
                    and name.lower().endswith((
                        ".mp4",
                        ".m4a",
                        ".mp3",
                        ".mkv",
                        ".webm",
                        ".jpg",
                        ".jpeg",
                        ".png",
                    ))
                ):
                    results.append(path)
        except OSError:
            pass

        results.sort(
            key=lambda path: os.path.getmtime(path),
            reverse=True,
        )
        return results

    def show_mine(self):
        self.page_name = "mine"
        self._scroll()
        self._nav()

        self.content.add_widget(
            self._label(
                "已下载",
                24,
                PINK,
                True,
                height=dp(44),
            )
        )
        self.content.add_widget(
            self._label(
                "下载完成的文件保存在应用目录，可导出到手机 Download/BiliPink。",
                12,
                MUTED,
                height=dp(42),
            )
        )
        self.content.add_widget(
            self._btn(
                "刷新列表",
                self.show_mine,
                PINK_LIGHT,
                TEXT,
                dp(42),
            )
        )

        files = self._list_downloaded_files()
        if not files:
            self.content.add_widget(
                self._label(
                    "还没有已下载的文件。\n完成下载后会显示在这里。",
                    13,
                    MUTED,
                    height=dp(76),
                )
            )

        for path in files:
            card = Surface(
                orientation="vertical",
                size_hint_y=None,
                padding=dp(12),
                spacing=dp(6),
            )
            card.bind(minimum_height=card.setter("height"))
            card.add_widget(
                self._label(
                    os.path.basename(path),
                    13,
                    TEXT,
                    True,
                    height=dp(44),
                )
            )

            try:
                size = human_size(os.path.getsize(path))
            except OSError:
                size = "未知大小"

            card.add_widget(
                self._label(
                    size,
                    12,
                    MUTED,
                    height=dp(22),
                )
            )
            card.add_widget(
                self._btn(
                    "导出到手机 Download/BiliPink",
                    lambda current=path: self._export_file(current),
                    PINK,
                    WHITE,
                    dp(42),
                    True,
                )
            )
            card.add_widget(
                self._btn(
                    "删除应用内文件",
                    lambda current=path: self._confirm_delete_file(current),
                    WHITE,
                    RED,
                    dp(38),
                )
            )
            self.content.add_widget(card)

        self.content.add_widget(
            self._label(
                "应用内目录：\n" + self._downloads_dir(),
                10,
                MUTED,
                height=dp(52),
            )
        )

    def _export_file(self, source_path):
        if not os.path.isfile(source_path):
            self._popup("导出失败", "找不到要导出的文件。")
            return

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Environment = autoclass("android.os.Environment")
            activity = PythonActivity.mActivity

            downloads = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS
            )
            target_dir = os.path.join(
                str(downloads.getAbsolutePath()),
                "BiliPink",
            )
            os.makedirs(target_dir, exist_ok=True)

            filename = os.path.basename(source_path)
            target_path = os.path.join(target_dir, filename)

            if os.path.abspath(source_path) == os.path.abspath(target_path):
                self._popup("提示", "文件已经位于导出目录。")
                return

            if os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                target_path = os.path.join(
                    target_dir,
                    f"{name}_{int(time.time())}{ext}",
                )

            shutil.copy2(source_path, target_path)

            try:
                MediaScannerConnection = autoclass(
                    "android.media.MediaScannerConnection"
                )
                MediaScannerConnection.scanFile(
                    activity,
                    [target_path],
                    None,
                    None,
                )
            except Exception:
                pass

            self._popup(
                "导出成功",
                "文件已保存到：\n" + target_path,
            )

        except Exception as exc:
            self._popup(
                "导出失败",
                "导出时发生错误：\n" + str(exc),
            )

    def _confirm_delete_file(self, path):
        if not os.path.isfile(path):
            self._popup("提示", "文件不存在或已被删除。")
            self.show_mine()
            return

        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(14),
        )
        layout.add_widget(
            self._label(
                "确定要删除这个文件吗？\n\n" + os.path.basename(path),
                14,
                TEXT,
                height=dp(70),
            )
        )

        popup = Popup(
            title="删除文件",
            content=layout,
            size_hint=(0.88, None),
            height=dp(220),
        )

        buttons = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )
        buttons.add_widget(
            self._btn(
                "取消",
                popup.dismiss,
                WHITE,
                TEXT,
                dp(42),
            )
        )

        def delete_file():
            popup.dismiss()
            try:
                if os.path.isfile(path):
                    os.remove(path)
                self._popup("删除成功", "文件已删除。")
                self.show_mine()
            except Exception as exc:
                self._popup("删除失败", str(exc))

        buttons.add_widget(
            self._btn(
                "确认删除",
                delete_file,
                RED,
                WHITE,
                dp(42),
            )
        )
        layout.add_widget(buttons)
        popup.open()

    def _refresh_downloads(self):
        if self.page_name == "mine":
            self.show_mine()
        elif self.page_name == "home":
            self.show_home()

    def on_pause(self):
        return True

    def on_resume(self):
        self._refresh_downloads()

    def on_stop(self):
        try:
            self._save_tasks()
        except Exception:
            pass


if __name__ == "__main__":
    BiliPinkApp().run()
