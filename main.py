# -*- coding: utf-8 -*-
"""BiliPink v2.5.0 | Android | Bilibili downloader"""

import os

# Android SSL 证书配置
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
except ImportError:
    pass

import json
import time
import shutil
import threading
import urllib.request
from datetime import datetime

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

from bili_api import (
    get_video_info,
    get_download_options,
    bilibili_search,
)
from downloader import (
    download_stream,
    download_dash,
    merge_mp4,
    safe_filename,
    install_ffmpeg_from_assets,
)

PINK = (0.91, 0.39, 0.57, 1)
PINK_LIGHT = (1.0, 0.91, 0.95, 1)
WHITE = (1, 1, 1, 1)
BG = (0.985, 0.980, 0.985, 1)
TEXT = (0.31, 0.30, 0.32, 1)
MUTED = (0.52, 0.51, 0.53, 1)
GREEN = (0.30, 0.66, 0.40, 1)
RED = (0.82, 0.25, 0.30, 1)
FONT = "Roboto"
_FONT_LOADED = False

UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
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
        n = int(value or 0)
        if n >= 3600:
            return f"{n // 3600:02d}:{n % 3600 // 60:02d}:{n % 60:02d}"
        return f"{n // 60:02d}:{n % 60:02d}"
    except Exception:
        return "--:--"


def human_size(value):
    try:
        n = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"
    except Exception:
        return "未知大小"


class Surface(BoxLayout):
    def __init__(self, bg=WHITE, radius=dp(16), **kwargs):
        super().__init__(**kwargs)
        self._bg = bg
        self._radius = radius

        with self.canvas.before:
            Color(0, 0, 0, 0.055)
            self.shadow = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius],
            )
            Color(*bg)
            self.rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius],
            )

        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self.shadow.pos = (self.x, self.y - dp(2))
        self.shadow.size = self.size
        self.rect.pos = self.pos
        self.rect.size = self.size


class BiliPinkApp(App):
    title = "BiliPink"

    def build(self):
        Window.clearcolor = BG

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

        self._load_history()

        try:
            if platform == "android":
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
            size_hint_y=None,
            height=dp(62),
            padding=[dp(32), dp(4), dp(32), dp(4)],
            spacing=dp(55),
        )
        self.root_layout.add_widget(self.nav)

        Clock.schedule_once(self._load_cjk_font_safe, 0.2)
        self.show_home()
        return self.root_layout

    # -----------------------------------------------------
    # 字体与资源
    # -----------------------------------------------------
    def _extract_asset_to_file(self, asset_path, dest_path):
        if platform != "android":
            local = os.path.abspath(asset_path)
            return local if os.path.isfile(local) else None

        try:
            from jnius import autoclass

            activity_class = autoclass(
                "org.kivy.android.PythonActivity"
            )
            activity = activity_class.mActivity
            stream = activity.getAssets().open(asset_path)

            os.makedirs(
                os.path.dirname(dest_path),
                exist_ok=True,
            )

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

        if self.page_name == "home":
            self.show_home()
        else:
            self.show_mine()

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

    # -----------------------------------------------------
    # 通用控件
    # -----------------------------------------------------
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
            height=dp(height or max(25, size * 1.8)),
        )

        label.bind(
            size=lambda obj, *_:
            setattr(obj, "text_size", (obj.width, None))
        )
        return label

    def _btn(
        self,
        text,
        callback,
        color=WHITE,
        fg=TEXT,
        height=dp(44),
        bold=False,
    ):
        button = Button(
            text=text,
            font_name=FONT,
            font_size=dp(14),
            bold=bold,
            background_normal="",
            background_down="",
            background_color=color,
            color=fg,
            size_hint_y=None,
            height=height,
        )
        button.bind(on_release=lambda *_: callback())
        return button

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

        for key, caption in (
            ("home", "主页"),
            ("mine", "我的"),
        ):
            active = self.page_name == key
            color = PINK if active else MUTED

            cell = BoxLayout(
                orientation="vertical",
                spacing=0,
            )

            button = Button(
                text="",
                font_name=FONT,
                font_size=dp(24),
                background_normal="",
                background_color=(0, 0, 0, 0),
                color=color,
            )
            label = Label(
                text=caption,
                font_name=FONT,
                font_size=dp(12),
                color=color,
            )

            def goto_page(_instance, selected=key):
                if selected == "home":
                    self.show_home()
                else:
                    self.show_mine()

            button.bind(on_release=goto_page)
            label.bind(
                on_touch_down=lambda obj, touch, k=key:
                self._nav_touch(obj, touch, k)
            )

            cell.add_widget(button)
            cell.add_widget(label)
            self.nav.add_widget(cell)

    def _nav_touch(self, obj, touch, page):
        if obj.collide_point(*touch.pos):
            if page == "home":
                self.show_home()
            else:
                self.show_mine()
            return True
        return False

    def _popup(self, title, message):
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
            title=title,
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

    # -----------------------------------------------------
    # 首页
    # -----------------------------------------------------
    def show_home(self):
        self.page_name = "home"
        self._scroll()
        self._nav()

        top = BoxLayout(
            size_hint_y=None,
            height=dp(60),
            spacing=dp(10),
        )

        avatar_path = self._load_avatar()
        if avatar_path and os.path.isfile(avatar_path):
            avatar = Image(
                source=avatar_path,
                fit_mode="contain",
                size_hint_x=None,
                width=dp(48),
            )
        else:
            avatar = Label(
                text="",
                font_name=FONT,
                color=PINK,
                size_hint_x=None,
                width=dp(44),
            )

        top.add_widget(avatar)

        search = BoxLayout(
            size_hint_y=None,
            height=dp(46),
            padding=[dp(10), dp(2)],
            spacing=dp(5),
        )

        with search.canvas.before:
            Color(*WHITE)
            search.bg = RoundedRectangle(
                pos=search.pos,
                size=search.size,
                radius=[dp(22)],
            )
            Color(0.88, 0.85, 0.87, 1)
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
            hint_text="输入BV / AV / 链接 / 关键词",
            font_name=FONT,
            font_size=dp(15),
            multiline=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            cursor_color=PINK,
            padding=[dp(3), dp(10)],
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
        top.add_widget(search)
        self.content.add_widget(top)

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
                self.content.add_widget(
                    self._search_result_card(item)
                )

        visible = []
        for task in self.tasks:
            status = task.get("status", "")

            if self.filter == "全部":
                visible.append(task)
            elif self.filter == "已完成" and status == "已完成":
                visible.append(task)
            elif self.filter == "进行中" and status in (
                "解析中", "等待下载", "下载中", "合并中"
            ):
                visible.append(task)
            elif self.filter == "已失败" and status == "已失败":
                visible.append(task)

        if self.filter in ("全部", "已完成"):
            for record in self.history:
                if not any(
                    item.get("id") == record.get("id")
                    for item in visible
                ):
                    visible.append({
                        **record,
                        "status": "已完成",
                    })

        visible.sort(
            key=lambda item: item.get("created", ""),
            reverse=True,
        )

        if not visible and not self.search_result_list:
            self.content.add_widget(
                self._label(
                    "输入BV号、AV号、B站链接或关键词开始",
                    13,
                    MUTED,
                    False,
                    "center",
                    dp(90),
                )
            )

        for task in visible:
            self.content.add_widget(self._task_card(task))

    def set_filter(self, value):
        self.filter = value
        self.show_home()

    # -----------------------------------------------------
    # 搜索
    # -----------------------------------------------------
    def do_search_or_parse(self):
        text = self.search_input.text.strip()

        if not text:
            self._popup("提示", "请先输入BV号、AV号、链接或关键词。")
            return

        upper = text.upper()
        has_video_id = "BV" in upper or "AV" in upper
        has_link = "BILIBILI.COM" in upper or "B23.TV" in upper

        if has_video_id or has_link:
            self.search_result_list = []
            self.parse_video()
            return

        if self.busy:
            self._popup("请稍候", "当前有任务正在处理。")
            return
            self.busy = True
        self.content.add_widget(
            self._label("正在搜索……", 13, MUTED, height=dp(35))
        )

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
            result = []
            error = str(exc)

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
            self._popup("提示", "搜索结果没有提供BV号。")
            return

        self.search_input.text = bvid
        self.search_result_list = []
        self.parse_video()

    # -----------------------------------------------------
    # 解析视频
    # -----------------------------------------------------
    def _find_task(self, task_id):
        return next(
            (
                task for task in self.tasks
                if task.get("id") == task_id
            ),
            None,
        )

    def parse_video(self):
        if self.busy:
            self._popup("请稍候", "当前已有解析或搜索任务。")
            return

        raw = self.search_input.text.strip()
        if not raw:
            self._popup("提示", "请先输入视频链接。")
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

            cover_url = info.get("cover", info.get("thumbnail", ""))
            if cover_url:
                try:
                    cover_dir = os.path.join(
                        self.user_data_dir,
                        "covers",
                    )
                    os.makedirs(cover_dir, exist_ok=True)

                    cover_name = safe_filename(
                        info.get("bvid", "video")
                    ) + ".jpg"
                    cover_path = os.path.join(cover_dir, cover_name)

                    if not os.path.isfile(cover_path):
                        request = urllib.request.Request(
                            cover_url,
                            headers={
                                "User-Agent": UA,
                                "Referer": "https://www.bilibili.com/",
                            },
                        )

                        with urllib.request.urlopen(
                            request,
                            timeout=20,
                        ) as response:
                            data = response.read()

                        if data:
                            with open(cover_path, "wb") as file:
                                file.write(data)

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
        if task is None:
            return

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
        # -----------------------------------------------------
    # 视频信息与画质选择
    # -----------------------------------------------------
    def show_video_options(self):
        info = self.current_info or {}
        options = self.current_options or []
        self._scroll()
        self._nav()

        self.content.add_widget(
            self._label("视频详情", 22, PINK, True, height=dp(42))
        )
        self.content.add_widget(
            self._label(
                info.get("title", "未命名视频"),
                17,
                TEXT,
                True,
                height=dp(56),
            )
        )

        owner = info.get("owner", {})
        if isinstance(owner, dict):
            author = owner.get(
                "name",
                info.get("author", "未知UP主"),
            )
        else:
            author = str(owner or info.get("author", "未知UP主"))

        details = [
            ("BV号", info.get("bvid", "未知")),
            ("AV号", info.get("aid", "未知")),
            ("UP主", author),
            ("UID", info.get("mid", "未知")),
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
                    13,
                    TEXT,
                    height=dp(25),
                )
            )

        self.content.add_widget(card)

        description = info.get("desc", info.get("description", ""))
        if description:
            self.content.add_widget(
                self._label("视频简介", 15, PINK, True, height=dp(32))
            )
            self.content.add_widget(
                self._label(
                    str(description)[:1500],
                    12,
                    MUTED,
                    height=dp(100),
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
                    "没有获取到可下载画质。请检查 bili_api.py 的返回结果，"
                    "以及该视频是否允许访问。",
                    13,
                    RED,
                    height=dp(70),
                )
            )

        for option in options:
            self.content.add_widget(
                self._btn(
                    self._option_label(option),
                    lambda selected=option:
                    self._confirm_download(selected),
                    PINK_LIGHT,
                    TEXT,
                    dp(46),
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

        if kind in ("dash", "mp4_dash"):
            kind_text = "DASH音视频"
        elif "audio" in kind:
            kind_text = "音频"
        else:
            kind_text = "视频"

        size = option.get("size", option.get("filesize", 0))
        try:
            size_text = (
                " · " + human_size(size)
                if float(size or 0) > 0
                else ""
            )
        except Exception:
            size_text = ""

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
                height=dp(50),
            )
        )
        layout.add_widget(
            self._label(
                "确认后开始下载。DASH 画质需要 FFmpeg 合并音视频。",
                12,
                MUTED,
                height=dp(46),
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
            self._btn(
                "取消",
                popup.dismiss,
                WHITE,
                TEXT,
                dp(40),
            )
        )
        row.add_widget(
            self._btn(
                "开始下载",
                lambda: self._begin_download_after_popup(
                    popup,
                    option,
                ),
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

    # -----------------------------------------------------
    # 下载任务管理
    # -----------------------------------------------------
    def _start_download(self, option):
        info = self.current_info or {}
        if not info:
            self._popup("无法下载", "请先解析视频。")
            return

        task_id = str(time.time_ns())
        title = info.get("title", "BiliPink_video")
        bvid = info.get("bvid", "video")

        task = {
            "id": task_id,
            "title": title,
            "bvid": bvid,
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
            args=(task_id, info, option),
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
            lambda _dt: self.show_home(),
            0,
        )

    def _set_task_progress(self, task_id, percent):
        task = self._find_task(task_id)
        if task:
            task["percent"] = max(0, min(100, float(percent)))

    def _download_worker(self, task_id, info, option):
        task = self._find_task(task_id)
        if not task:
            return

        save_dir = self._downloads_dir()
        title = safe_filename(info.get("title", "BiliPink_video"))
        bvid = safe_filename(info.get("bvid", "video"))

        output_path = os.path.join(
            save_dir,
            f"{title}_{bvid}.mp4",
        )

        # 避免覆盖已经存在的文件。
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

        def on_progress(downloaded, total):
            if is_cancelled():
                return

            if total and total > 0:
                percent = min(97, downloaded * 97.0 / total)
            else:
                percent = 0

            Clock.schedule_once(
                lambda _dt, p=percent:
                self._set_task_progress(task_id, p),
                0,
            )

        video_temp = ""
        audio_temp = ""

        try:
            is_dash = (
                option_type in ("dash", "mp4_dash")
                or bool(audio_url)
            )

            if is_dash:
                if not video_url or not audio_url:
                    raise ValueError(
                        "DASH 选项缺少 video_url 或 audio_url。"
                        "请检查 bili_api.py 返回的画质数据。"
                    )

                video_temp = os.path.join(
                    save_dir,
                    f".{task_id}.video.part",
                )
                audio_temp = os.path.join(
                    save_dir,
                    f".{task_id}.audio.part",
                )

                self._set_task_status(task_id, "下载中", 0)

                download_dash(
                    video_url,
                    audio_url,
                    video_temp,
                    audio_temp,
                    progress=on_progress,
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
                        "该画质没有视频流 URL，"
                        "请检查 bili_api.py 返回字段。"
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

            if not os.path.isfile(output_path):
                raise IOError("下载结束但没有找到输出文件。")

            if os.path.getsize(output_path) <= 0:
                raise IOError("输出文件为空。")

            Clock.schedule_once(
                lambda _dt:
                self._download_done(task_id, output_path),
                0,
            )

        except Exception as exc:
            message = str(exc)
            if isinstance(exc, InterruptedError):
                message = "任务已取消"

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

        task["status"] = "已完成"
        task["percent"] = 100
        task["path"] = path
        task["error"] = ""
        task["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cancel_flags.pop(task_id, None)
        self._add_history(task)
        self.show_home()

        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "未知大小"

        self._popup(
            "下载完成",
            f"{task.get('title', '视频')}\n\n"
            f"保存位置：\n{path}\n\n"
            f"文件大小：{size}",
        )

    def _download_error(self, task_id, message):
        task = self._find_task(task_id)
        if not task:
            return

        task["status"] = "已失败"
        task["error"] = str(message)
        self.cancel_flags.pop(task_id, None)

        self.show_home()
        self._popup("下载失败", message)

    # 修复点：取消下载方法和下面的任务卡片区域分开。
    def cancel_download(self, task_id):
        event = self.cancel_flags.get(task_id)
        if event:
            event.set()
            self._popup(
                "已请求取消",
                "下载线程将在下一次检查时停止。",
            )
            # -----------------------------------------------------
    # 任务卡片与详情
    # -----------------------------------------------------
    def _task_card(self, task):
        card = Surface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(105),
            padding=dp(9),
            spacing=dp(10),
        )

        cover_path = task.get("cover_path", "")
        if cover_path and os.path.isfile(cover_path):
            card.add_widget(
                Image(
                    source=cover_path,
                    fit_mode="cover",
                    size_hint_x=None,
                    width=dp(90),
                )
            )
        else:
            placeholder = FloatLayout(
                size_hint_x=None,
                width=dp(90),
            )

            with placeholder.canvas.before:
                Color(*PINK_LIGHT)
                placeholder.rect = RoundedRectangle(
                    pos=placeholder.pos,
                    size=placeholder.size,
                    radius=[dp(10)],
                )

            placeholder.bind(
                pos=lambda obj, *_:
                setattr(obj.rect, "pos", obj.pos),
                size=lambda obj, *_:
                setattr(obj.rect, "size", obj.size),
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
            GREEN if status == "已完成"
            else RED if status == "已失败"
            else PINK
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
        path = task.get("path", "")

        message = (
            f"标题：{task.get('title', '视频')}\n"
            f"状态：{task.get('status', '未知')}\n"
            f"任务时间：{task.get('created', '')}\n"
        )

        if path:
            message += f"\n文件：{path}\n"
            try:
                message += f"大小：{human_size(os.path.getsize(path))}"
            except OSError:
                message += "大小：文件不可访问"

        if task.get("error"):
            message += "\n\n错误信息：\n" + task["error"]

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
            self._btn(
                "关闭",
                popup.dismiss,
                PINK,
                WHITE,
                dp(40),
            )
        )

        layout.add_widget(row)
        popup.open()

    # -----------------------------------------------------
    # 下载历史
    # -----------------------------------------------------
    def _history_path(self):
        return os.path.join(self.user_data_dir, "history.json")

    def _load_history(self):
        try:
            with open(
                self._history_path(),
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            self.history = data if isinstance(data, list) else []
        except Exception:
            self.history = []

    def _save_history(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)

            temp_path = self._history_path() + ".tmp"
            with open(
                temp_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    self.history,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            os.replace(temp_path, self._history_path())
        except Exception:
            pass

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

    # -----------------------------------------------------
    # 我的页面：已下载与导出
    # -----------------------------------------------------
    def _list_downloaded_files(self):
        folder = self._downloads_dir()
        results = []

        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)

                if (
                    os.path.isfile(path)
                    and not name.endswith(".part")
                    and name.lower().endswith(
                        (".mp4", ".m4a", ".mp3", ".mkv", ".webm")
                    )
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
            self._label("我的", 24, PINK, True, height=dp(44))
        )
        self.content.add_widget(
            self._label(
                "BiliPink 下载管理",
                13,
                MUTED,
                height=dp(28),
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
        self.content.add_widget(
            self._label(
                "已下载文件",
                17,
                PINK,
                True,
                height=dp(38),
            )
        )

        files = self._list_downloaded_files()

        if not files:
            self.content.add_widget(
                self._label(
                    "还没有已下载的文件。\n"
                    "完成下载后，文件会显示在这里。",
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
                    "导出到手机 Download 文件夹",
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
                    lambda current=path:
                    self._confirm_delete_file(current),
                    WHITE,
                    RED,
                    dp(38),
                )
            )

            self.content.add_widget(card)

        self.content.add_widget(
            self._label(
                "应用内下载目录：\n" + self._downloads_dir(),
                10,
        MUTED,
                height=dp(52),
            )
        )

    def _export_file(self, source_path):
        if not os.path.isfile(source_path):
            self._popup("导出失败", "源文件不存在。")
            return

        try:
            if platform == "android":
                from android.storage import primary_external_storage_path

                target_dir = os.path.join(
                    primary_external_storage_path(),
                    "Download",
                    "BiliPink",
                )
            else:
                target_dir = os.path.join(
                    os.path.expanduser("~"),
                    "Downloads",
                    "BiliPink",
                )

            os.makedirs(target_dir, exist_ok=True)

            name = os.path.basename(source_path)
            destination = os.path.join(target_dir, name)

            if os.path.abspath(destination) == os.path.abspath(source_path):
                self._popup("提示", "文件已经在目标目录中。")
                return

            if os.path.exists(destination):
                stem, ext = os.path.splitext(name)
                destination = os.path.join(
                    target_dir,
                    f"{stem}_{int(time.time())}{ext}",
                )

            shutil.copy2(source_path, destination)

            self._popup(
                "导出完成",
                f"文件已复制到：\n{destination}",
            )

        except Exception as exc:
            self._popup(
                "导出失败",
                f"{exc}\n\n"
                "Android 版本可能需要额外的存储授权。"
                "如果系统拒绝直接写入，请使用系统文件管理器复制。",
            )

    def _confirm_delete_file(self, path):
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(14),
        )

        layout.add_widget(
            self._label(
                "确定删除这个应用内文件吗？\n"
                "如果没有备份，删除后无法恢复。",
                13,
                TEXT,
                height=dp(65),
            )
        )

        popup = Popup(
            title="确认删除",
            content=layout,
            size_hint=(0.88, 0.36),
        )

        row = BoxLayout(
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )

        row.add_widget(
            self._btn(
                "取消",
                popup.dismiss,
                WHITE,
                TEXT,
                dp(40),
            )
        )
        row.add_widget(
            self._btn(
                "删除",
                lambda: self._delete_file(path, popup),
                RED,
                WHITE,
                dp(40),
                True,
            )
        )

        layout.add_widget(row)
        popup.open()

    def _delete_file(self, path, popup):
        popup.dismiss()

        try:
            if os.path.isfile(path):
                os.remove(path)

            for record in self.history:
                if record.get("path") == path:
                    record["path"] = ""

            self._save_history()
            self.show_mine()

        except Exception as exc:
            self._popup("删除失败", str(exc))


if __name__ == "__main__":
    BiliPinkApp().run()
