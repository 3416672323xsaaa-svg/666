# -*- coding: utf-8 -*-
"""BiliPink v2.5.0 | Kivy Android | Bilibili downloader | DASH support"""

import json
import os
import shutil
import threading
import urllib.request
import time
import hashlib
import subprocess
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp
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
from kivy.utils import platform

from bili_api import get_video_info, get_download_options, bilibili_search
from downloader import download_stream, safe_filename

try:
    from downloader import merge_streams
except Exception:
    merge_streams = None


PINK = (0.91, 0.39, 0.57, 1)
PINK_LIGHT = (1.0, 0.91, 0.95, 1)
WHITE = (1, 1, 1, 1)
BG = (1, 1, 1, 1)
TEXT = (0.31, 0.30, 0.32, 1)
MUTED = (0.52, 0.51, 0.53, 1)
GREEN = (0.30, 0.66, 0.40, 1)
RED = (0.82, 0.25, 0.30, 1)
BORDER = (0.90, 0.89, 0.90, 1)

FONT = None
_FONT_LOADED = False

UA = (
    "Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


def fmt_num(n):
    try:
        n = int(n or 0)
        if n >= 100000000:
            return f"{n / 100000000:.1f}亿"
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(n)
    except Exception:
        return str(n or 0)


def fmt_time(n):
    try:
        n = int(n)
        if n >= 3600:
            return f"{n // 3600:02d}:{n % 3600 // 60:02d}:{n % 60:02d}"
        return f"{n // 60:02d}:{n % 60:02d}"
    except Exception:
        return "--:--"


def human_size(n):
    try:
        n = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.1f} {unit}"
            n /= 1024
    except Exception:
        return "未知大小"


class Surface(BoxLayout):

    def __init__(self, bg=WHITE, radius=dp(16), **kwargs):
        super().__init__(**kwargs)
        self._bg = bg
        self._radius = radius

        with self.canvas.before:
            Color(0, 0, 0, 0.075)
            self.shadow_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius]
            )

            Color(*bg)
            self.main_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius]
            )

        self.bind(pos=self._draw_update, size=self._draw_update)

    def _draw_update(self, *args):
        self.shadow_rect.pos = (self.x, self.y - dp(2))
        self.shadow_rect.size = self.size
        self.main_rect.pos = self.pos
        self.main_rect.size = self.size


class BiliPinkApp(App):

    title = "BiliPink"

    def build(self):
        Window.clearcolor = BG

        self.busy = False
        self.current_info = None
        self.current_options = []
        self.history = []
        self.tasks = []
        self.filter = "全部"
        self.page_name = "home"
        self.search_result_list = []

        self.root_layout = BoxLayout(
            orientation="vertical",
            spacing=0
        )

        self.body = BoxLayout(
            orientation="vertical"
        )

        self.root_layout.add_widget(self.body)

        self.nav = BoxLayout(
            size_hint_y=None,
            height=dp(66),
            padding=[dp(36), dp(5), dp(36), dp(4)],
            spacing=dp(65)
        )

        self.root_layout.add_widget(self.nav)

        self.show_home()

        Clock.schedule_once(
            self._load_cjk_font_safe,
            0.12
        )

        return self.root_layout

    # ---------------------------------------------------------
    # 字体
    # ---------------------------------------------------------

    def _extract_asset_to_file(self, asset_fullpath, dest_path):

        if platform != "android":
            local_p = os.path.abspath(asset_fullpath)

            if os.path.isfile(local_p):
                return local_p

            return None

        try:
            from jnius import autoclass

            PythonActivity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            ctx = PythonActivity.mActivity
            asset_mgr = ctx.getAssets()

            stream = asset_mgr.open(asset_fullpath)

            buffer = bytearray()

            while True:
                chunk = stream.read(8192)

                if chunk <= 0:
                    break

                buffer.extend(chunk)

            stream.close()

            os.makedirs(
                os.path.dirname(dest_path),
                exist_ok=True
            )

            with open(dest_path, "wb") as f:
                f.write(buffer)

            return dest_path

        except Exception:
            return None

    def _load_cjk_font_safe(self, dt):

        global FONT
        global _FONT_LOADED

        if _FONT_LOADED:
            return

        try:

            from android.storage import app_storage_path

            cache_font_path = os.path.join(
                app_storage_path(),
                "NotoSansSC-Regular.otf"
            )

            if os.path.isfile(cache_font_path):
                fp = cache_font_path
            else:
                fp = self._extract_asset_to_file(
                    "fonts/NotoSansSC-Regular.otf",
                    cache_font_path
                )

            if fp and os.path.isfile(fp):

                LabelBase.register(
                    name="BiliCJK",
                    fn_regular=fp,
                    fn_bold=fp,
                    fn_italic=fp,
                    fn_bolditalic=fp
                )

                FONT = "BiliCJK"
                _FONT_LOADED = True

                if self.page_name == "home":
                    self.show_home()
                else:
                    self.show_mine()

            else:

                FONT = "Roboto"
                _FONT_LOADED = True

        except Exception:

            FONT = "Roboto"
            _FONT_LOADED = True

    def _load_avatar(self):

        try:

            if platform != "android":
                p = os.path.abspath(
                    "fonts/avatar-reference.jpg"
                )

                return p if os.path.isfile(p) else None

            from android.storage import app_storage_path

            cache_ava = os.path.join(
                app_storage_path(),
                "avatar-reference.jpg"
            )

            if os.path.isfile(cache_ava):
                return cache_ava

            return self._extract_asset_to_file(
                "fonts/avatar-reference.jpg",
                cache_ava
            )

        except Exception:
            return None

    # ---------------------------------------------------------
    # 基础 UI
    # ---------------------------------------------------------

    def _label(
        self,
        text,
        size=14,
        color=TEXT,
        bold=False,
        halign="left",
        height=None
    ):

        h = height or max(24, size * 1.75)

        use_font = FONT if FONT else "Roboto"

        w = Label(
            text=str(text),
            font_name=use_font,
            font_size=dp(size),
            color=color,
            bold=bold,
            halign=halign,
            valign="middle",
            size_hint_y=None,
            height=dp(h)
        )

        w.bind(
            size=lambda obj, *x:
            setattr(obj, "text_size", (obj.width, None))
        )

        return w

    def _btn(
        self,
        text,
        cb,
        color=WHITE,
        fg=TEXT,
        height=dp(44),
        bold=False
    ):

        use_font = FONT if FONT else "Roboto"

        b = Button(
            text=text,
            font_name=use_font,
            font_size=dp(14),
            bold=bold,
            background_normal="",
            background_down="",
            background_color=color,
            color=fg,
            size_hint_y=None,
            height=height
        )

        b.bind(
            on_release=lambda *a: cb()
        )

        return b

    def _scroll(self):

        self.body.clear_widgets()

        self.scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(2),
            scroll_type=["bars", "content"]
        )

        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(13),
            padding=[
                dp(17),
                dp(10),
                dp(17),
                dp(15)
            ]
        )

        self.content.bind(
            minimum_height=self.content.setter("height")
        )

        self.scroll.add_widget(self.content)
        self.body.add_widget(self.scroll)

    def _nav(self):

        self.nav.clear_widgets()

        def goto(page):

            if page == "home":
                self.show_home()
            else:
                self.show_mine()

        for key, label, icon in (
            ("home", "主页", ""),
            ("mine", "我的", "")
        ):

            active = self.page_name == key

            c = (
                PINK
                if active
                else (0.48, 0.48, 0.49, 1)
            )

            box = BoxLayout(
                orientation="vertical",
                spacing=0
            )

            btn = Button(
                text=icon,
                font_name=FONT if FONT else "Roboto",
                font_size=dp(29),
                background_normal="",
                background_color=(0, 0, 0, 0),
                color=c,
                size_hint_y=0.62
            )

            cap = Label(
                text=label,
                font_name=FONT if FONT else "Roboto",
                font_size=dp(12),
                color=c,
                size_hint_y=0.38
            )

            btn.bind(
                on_release=lambda *a, k=key: goto(k)
            )

            cap.bind(
                on_touch_down=lambda inst, touch, k=key:
                goto(k)
                if inst.collide_point(*touch.pos)
                else None
            )

            box.add_widget(btn)
            box.add_widget(cap)

            self.nav.add_widget(box)

    # ---------------------------------------------------------
    # 首页
    # ---------------------------------------------------------

    def _search_draw(self, w):

        self.search_bg.pos = w.pos
        self.search_bg.size = w.size

        self.search_line.rounded_rectangle = (
            w.x,
            w.y,
            w.width,
            w.height,
            dp(25)
        )

    def _move_line(self, w):

        if hasattr(w, "_line"):
            w._line.pos = w.pos
            w._line.size = w.size

    def set_filter(self, val):

        self.filter = val
        self.show_home()

    def show_home(self):

        self.page_name = "home"

        self._scroll()
        self._nav()

        top = BoxLayout(
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10)
        )

        ava_p = self._load_avatar()

        if ava_p and os.path.isfile(ava_p):

            avatar = Image(
                source=ava_p,
                fit_mode="contain",
                size_hint_x=None,
                width=dp(48)
            )

        else:

            avatar = Label(
                text="",
                font_name=FONT if FONT else "Roboto",
                font_size=dp(33),
                color=PINK,
                size_hint_x=None,
                width=dp(42)
            )

        top.add_widget(avatar)

        search_wrap = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            padding=[dp(12), dp(1)],
            spacing=dp(5)
        )

        with search_wrap.canvas.before:

            Color(1, 1, 1, 1)

            self.search_bg = RoundedRectangle(
                pos=search_wrap.pos,
                size=search_wrap.size,
                radius=[dp(25)]
            )

            Color(0.48, 0.48, 0.49, 1)

            self.search_line = Line(
                rounded_rectangle=(
                    search_wrap.x,
                    search_wrap.y,
                    search_wrap.width,
                    search_wrap.height,
                    dp(25)
                ),
                width=1.1
            )

        search_wrap.bind(
            pos=self._search_draw,
            size=self._search_draw
        )

        search_icon = Button(
            text="",
            font_name=FONT if FONT else "Roboto",
            font_size=dp(27),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=(0.43, 0.43, 0.44, 1),
            size_hint_x=None,
            width=dp(32)
        )

        search_icon.bind(
            on_release=lambda *x:
            self.do_search_or_parse()
        )

        self.search_input = TextInput(
            hint_text="输入BV/AV/链接/关键词",
            font_name=FONT if FONT else "Roboto",
            font_size=dp(16),
            multiline=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            hint_text_color=(0.48, 0.48, 0.49, 1),
            cursor_color=PINK,
            padding=[dp(3), dp(10)]
        )

        self.search_input.bind(
            on_text_validate=
            lambda *x:
            self.do_search_or_parse()
        )

        search_wrap.add_widget(search_icon)
        search_wrap.add_widget(self.search_input)

        top.add_widget(search_wrap)

        self.content.add_widget(top)

        filters = BoxLayout(
            size_hint_y=None,
            height=dp(43),
            spacing=dp(6)
        )

        for fnam in (
            "全部",
            "已完成",
            "进行中",
            "已失败"
        ):

            col = (
                PINK
                if self.filter == fnam
                else MUTED
            )

            cell = BoxLayout(
                orientation="vertical",
                spacing=0
            )

            b = Button(
                text=fnam,
                font_name=FONT if FONT else "Roboto",
                font_size=dp(14),
                background_normal="",
                background_color=(0, 0, 0, 0),
                color=col
            )

            b.bind(
                on_release=
                lambda *x, v=fnam:
                self.set_filter(v)
            )

            cell.add_widget(b)

            underline = Widget(
                size_hint_y=None,
                height=dp(3)
            )

            with underline.canvas:

                Color(
                    *(
                        PINK
                        if self.filter == fnam
                        else (1, 1, 1, 0)
                    )
                )

                underline._line = RoundedRectangle(
                    pos=underline.pos,
                    size=underline.size,
                    radius=[dp(2)]
                )

            underline.bind(
                pos=self._move_line,
                size=self._move_line
            )

            cell.add_widget(underline)
            filters.add_widget(cell)

        self.content.add_widget(filters)

        if self.search_result_list:

            self.content.add_widget(
                self._label(
                    "搜索结果",
                    15,
                    TEXT,
                    True,
                    "left",
                    dp(36)
                )
            )

            for item in self.search_result_list:
                self.content.add_widget(
                    self._search_result_card(item)
                )

        if (
            self.filter == "全部"
            and not self.tasks
            and not self.history
            and not self.search_result_list
        ):

            self.content.add_widget(
                self._label(
                    "输入BV / AV / 链接或者中文关键词开始",
                    13,
                    MUTED,
                    False,
                    "center",
                    dp(90)
                )
            )

        visible = []

        for tsk in self.tasks:

            s = tsk.get("status", "")

            if (
                self.filter == "全部"
                or (
                    self.filter == "已完成"
                    and s == "已完成"
                )
                or (
                    self.filter == "进行中"
                    and s in (
                        "解析中",
                        "下载中",
                        "等待下载",
                        "合并中"
                    )
                )
                or (
                    self.filter == "已失败"
                    and s == "已失败"
                )
            ):
                visible.append(tsk)

        if self.filter in ("全部", "已完成"):

            for hrec in self.history:

                if not any(
                    t.get("id") == hrec.get("id")
                    for t in visible
                ):

                    visible.append(
                        {
                            **hrec,
                            "status": "已完成"
                        }
                    )

        visible.sort(
            key=lambda x:
            x.get("created", ""),
            reverse=True
        )

        for item in visible:
            self.content.add_widget(
                self._task_card(item)
            )

    # ---------------------------------------------------------
    # 搜索
    # ---------------------------------------------------------

    def _search_result_card(self, it):

        card = Surface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(104),
            padding=0,
            spacing=0
        )

        thumb = BoxLayout(
            size_hint_x=None,
            width=dp(112)
        )

        cover_path = ""

        cache_dir = os.path.join(
            self.user_data_dir,
            "covers"
        )

        os.makedirs(
            cache_dir,
            exist_ok=True
        )

        local_cover = os.path.join(
            cache_dir,
            it["bvid"] + "_s.jpg"
        )

        if os.path.exists(local_cover):

            thumb.add_widget(
                Image(
                    source=local_cover,
                    fit_mode="cover"
                )
            )

        else:

            pl = FloatLayout()

            with pl.canvas.before:

                Color(0.92, 0.91, 0.91, 1)

                pl.bg = RoundedRectangle(
                    pos=pl.pos,
                    size=pl.size,
                    radius=[dp(12)]
                )

            pl.bind(
                pos=lambda w, *_:
                setattr(pl.bg, "pos", w.pos),
                size=lambda w, *_:
                setattr(pl.bg, "size", w.size)
            )

            pl.add_widget(
                Label(
                    text="",
                    font_name=FONT if FONT else "Roboto",
                    font_size=dp(14),
                    bold=True,
                    color=PINK
                )
            )

            thumb.add_widget(pl)

        card.add_widget(thumb)

        info = BoxLayout(
            orientation="vertical",
            padding=[
                dp(12),
                dp(7),
                dp(10),
                dp(5)
            ],
            spacing=dp(2)
        )

        info.add_widget(
            self._label(
                it.get("title", "未命名视频"),
                14,
                PINK,
                True,
                height=dp(34)
            )
        )

        sub = (
            f"{it.get('duration', '--:--')} | "
            f"{it.get('pubdate', '')} | "
            f"UP:{it.get('author', '')}"
        )

        info.add_widget(
            self._label(
                sub,
                11,
                MUTED,
                height=dp(21)
            )
        )

        row = BoxLayout(
            size_hint_y=None,
            height=dp(32),
            spacing=dp(6)
        )

        row.add_widget(
            self._btn(
                "选择解析",
                lambda bv=it["bvid"]:
                self.parse_by_bvid(bv),
                PINK,
                WHITE,
                dp(36),
                True
            )
        )

        info.add_widget(row)

        card.add_widget(info)

        return card

    def parse_by_bvid(self, bvid):

        self.search_input.text = bvid
        self.search_result_list.clear()
        self.parse_video()

    def do_search_or_parse(self):

        txt = self.search_input.text.strip()

        if not txt:
            return

        has_bv = "BV" in txt.upper()
        has_av = "av" in txt.lower()

        has_link = (
            "bilibili.com" in txt
            or "b23.tv" in txt
        )

        if has_bv or has_av or has_link:

            self.search_result_list.clear()
            self.parse_video()

        else:

            if self.busy:
                return

            self.busy = True

            threading.Thread(
                target=self._search_worker,
                args=(txt,),
                daemon=True
            ).start()

    def _search_worker(self, kw):

        try:
            res = bilibili_search(kw)
        except Exception as e:
            res = []

        Clock.schedule_once(
            lambda dt:
            self._search_done(res),
            0
        )

    def _search_done(self, res):

        self.busy = False
        self.search_result_list = res or []
        self.show_home()

    # ---------------------------------------------------------
    # 任务卡片
    # ---------------------------------------------------------

    def _task_card(self, t):

        card = Surface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(100),
            padding=0,
            spacing=0
        )

        thumb = BoxLayout(
            size_hint_x=None,
            width=dp(112)
        )

        cover = t.get("cover_path", "")

        if cover and os.path.isfile(cover):

            thumb.add_widget(
                Image(
                    source=cover,
                    fit_mode="cover"
                )
            )

        else:

            pl = FloatLayout()

            with pl.canvas.before:

                Color(0.92, 0.91, 0.91, 1)

                pl.bg = RoundedRectangle(
                    pos=pl.pos,
                    size=pl.size,
                    radius=[dp(12)]
                )

            pl.bind(
                pos=lambda w, *_:
                setattr(pl.bg, "pos", w.pos),
                size=lambda w, *_:
                setattr(pl.bg, "size", w.size)
            )

            thumb.add_widget(pl)

        card.add_widget(thumb)

        info = BoxLayout(
            orientation="vertical",
            padding=[
                dp(12),
                dp(7),
                dp(10),
                dp(5)
            ],
            spacing=dp(2)
        )

        title = t.get(
            "title",
            "正在解析视频…"
        )

        info.add_widget(
            self._label(
                title,
                14,
                PINK,
                True,
                height=dp(36)
            )
        )

        subtext = (
            t.get("time")
            or t.get("created")
            or datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        info.add_widget(
            self._label(
                subtext,
                11,
                MUTED,
                height=dp(21)
            )
        )

        row = BoxLayout(
            size_hint_y=None,
            height=dp(24),
            spacing=dp(5)
        )

        stat = t.get(
            "status",
            "已完成"
        )

        stat_color = (
            GREEN
            if stat == "已完成"
            else (
                RED
                if stat == "已失败"
                else PINK
            )
        )

        row.add_widget(
            self._label(
                stat,
                12,
                stat_color,
                True,
                height=dp(24)
            )
        )

        if stat in (
            "下载中",
            "解析中",
            "等待下载",
            "合并中"
        ):

            row.add_widget(
                self._label(
                    f"{t.get('percent', 0):.0f}%",
                    11,
                    MUTED,
                    False,
                    "right",
                    dp(24)
                )
            )

        info.add_widget(row)

        if stat in (
            "下载中",
            "解析中",
            "等待下载",
            "合并中"
        ):

            pb = ProgressBar(
                max=100,
                value=t.get("percent", 0),
                size_hint_y=None,
                height=dp(4)
            )

            info.add_widget(pb)

        card.add_widget(info)

        card.bind(
            on_touch_down=
            lambda w, touch, task=t:
            self._show_task(task)
            if w.collide_point(*touch.pos)
            else None
        )

        return card

    def _show_task(self, t):

        if (
            t.get("path")
            and os.path.isfile(t["path"])
        ):

            self._popup(
                "下载任务",
                f"{t.get('title', '视频')}\n\n"
                f"状态：{t.get('status', '已完成')}\n"
                f"文件：{t.get('path', '')}\n"
                f"大小：{human_size(os.path.getsize(t['path']))}"
            )

        elif t.get("error"):

            self._popup(
                "任务失败",
                t["error"]
            )

        else:

            self._popup(
                "下载任务",
                f"{t.get('title', '视频')}\n"
                f"状态：{t.get('status', '处理中')}"
            )

    # ---------------------------------------------------------
    # 解析
    # ---------------------------------------------------------

    def parse_video(self):

        if self.busy:

            self._popup(
                "请稍候",
                "当前已有解析或下载任务，请稍候。"
            )

            return

        raw = self.search_input.text.strip()

        if not raw:

            self._popup(
                "输入视频链接",
                "请粘贴B站视频链接，或输入BV / AV号。"
            )

            return

        self.busy = True

        tid = str(
            datetime.now().timestamp()
        )

        newtsk = {
            "id": tid,
            "title": "正在解析视频…",
            "status": "解析中",
            "created": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "percent": 0
        }

        self.tasks.insert(
            0,
            newtsk
        )

        self.show_home()

        threading.Thread(
            target=self._parse_worker,
            args=(raw, tid),
            daemon=True
        ).start()

    def _parse_worker(
        self,
        raw,
        taskid
    ):

        try:

            info = get_video_info(raw)

            options = get_download_options(
                info,
                ""
            )

            cover_path = ""

            try:

                cache_dir = os.path.join(
                    self.user_data_dir,
                    "covers"
                )

                os.makedirs(
                    cache_dir,
                    exist_ok=True
                )

                cover_path = os.path.join(
                    cache_dir,
                    info["bvid"] + ".jpg"
                )

                if not os.path.isfile(cover_path):

                    req = urllib.request.Request(
                        info["cover"],
                        headers={
                            "User-Agent": UA,
                            "Referer":
                            "https://www.bilibili.com/"
                        }
                    )

                    with urllib.request.urlopen(
                        req,
                        timeout=15
                    ) as r:

                        with open(
                            cover_path,
                            "wb"
                        ) as f:
                            f.write(r.read())

            except Exception:
                cover_path = ""

            Clock.schedule_once(
                lambda dt:
                self._parsed(
                    taskid,
                    info,
                    options,
                    cover_path
                ),
                0
            )

        except Exception as e:

            Clock.schedule_once(
                lambda dt, msg=str(e):
                self._parse_error(
                    taskid,
                    msg
                ),
                0
            )

    def _find_task(self, tid):

        return next(
            (
                x
                for x in self.tasks
                if x.get("id") == tid
            ),
            None
        )
def _parsed(self, taskid, info, options, cover_path):
        self.busy = False
        self.current_info = info
        self.current_options = options

        task = self._find_task(taskid)
        if task is None:
            return

        task.update({
            "title": info.get("title", "BiliPink Video"),
            "cover_path": cover_path,
            "bvid": info.get("bvid", ""),
            "aid": info.get("aid", ""),
            "status": "等待下载",
            "percent": 0,
            "info": info,
        })

        self.show_home()
        self._quality_popup(taskid, info, options)

    def _parse_error(self, taskid, message):
        self.busy = False
        task = self._find_task(taskid)

        if task:
            task.update({
                "status": "已失败",
                "error": str(message),
                "percent": 0,
            })

        self.show_home()
        self._popup("解析失败", str(message))

    def _quality_popup(self, taskid, info, options):
        box = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(14),
        )

        title = self._label(
            info.get("title", "视频信息"),
            16, PINK, True, height=dp(48)
        )
        box.add_widget(title)

        stats = (
            f"UP主：{info.get('owner', '未知')}\n"
            f"时长：{fmt_time(info.get('duration', 0))}\n"
            f"播放：{fmt_num(info.get('view', 0))}  "
            f"弹幕：{fmt_num(info.get('danmaku', 0))}\n"
            f"点赞：{fmt_num(info.get('like', 0))}  "
            f"收藏：{fmt_num(info.get('favorite', 0))}"
        )
        box.add_widget(self._label(
            stats, 12, MUTED, height=dp(82)
        ))
        box.add_widget(self._label(
            "选择实际获取到的画质",
            13, TEXT, True, height=dp(30)
        ))

        scroll = ScrollView(do_scroll_x=False)
        options_box = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            padding=[0, dp(2), 0, dp(4)],
        )
        options_box.bind(
            minimum_height=options_box.setter("height")
        )

        popup = Popup(
            title="选择下载画质",
            content=box,
            size_hint=(0.92, 0.82),
            auto_dismiss=True,
        )

        if not options:
            options_box.add_widget(self._label(
                "没有获取到可下载的画质，请重新解析。",
                13, RED, height=dp(52)
            ))

        for option in options:
            label = option.get("label", "未知画质")
            size = human_size(option.get("size", 0))
            stream_type = option.get("type", "mp4").upper()

            btn = self._btn(
                f"{label}  ·  {stream_type}  ·  {size}",
                lambda opt=option: self._start_task_download(
                    taskid, opt, popup
                ),
                PINK_LIGHT,
                PINK,
                dp(46),
                True,
            )
            options_box.add_widget(btn)

        scroll.add_widget(options_box)
        box.add_widget(scroll)

        box.add_widget(self._btn(
            "取消",
            popup.dismiss,
            WHITE,
            MUTED,
            dp(40),
        ))

        popup.open()

    def _start_task_download(self, taskid, option, popup=None):
        task = self._find_task(taskid)
        if not task:
            return

        if self.busy:
            self._popup("请稍候", "当前已有任务正在处理。")
            return

        self.busy = True

        task.update({
            "status": "下载中",
            "percent": 0,
            "error": "",
            "option_label": option.get("label", "视频"),
        })

        if popup:
            popup.dismiss()

        self.show_home()

        threading.Thread(
            target=self._download_worker,
            args=(taskid, dict(option)),
            daemon=True,
        ).start()

    def _download_worker(self, taskid, option):
        from downloader import download_stream

        task = self._find_task(taskid)
        if not task:
            Clock.schedule_once(
                lambda dt: self._download_finished_error(
                    taskid, "找不到下载任务。"
                ), 0
            )
            return

        try:
            download_dir = os.path.join(
                self.user_data_dir, "downloads"
            )
            os.makedirs(download_dir, exist_ok=True)

            name = safe_filename(task.get("title", "BiliPink Video"))
            bvid = task.get("bvid", "") or taskid.replace(".", "_")
            stem = f"{name}_{bvid}"

            last_refresh = [0.0]

            def progress(done, total):
                if total > 0:
                    percent = min(99.0, done * 100.0 / total)
                else:
                    percent = 0.0

                now = time.time()
                if now - last_refresh[0] >= 0.35:
                    last_refresh[0] = now
                    Clock.schedule_once(
                        lambda dt, p=percent:
                        self._download_progress(taskid, p),
                        0
                    )

            if option.get("type") == "dash":
                from downloader import download_dash, merge_mp4

                video_path = os.path.join(
                    download_dir, stem + "_video.m4s"
                )
                audio_path = os.path.join(
                    download_dir, stem + "_audio.m4s"
                )
                output_path = os.path.join(
                    download_dir, stem + ".mp4"
                )

                Clock.schedule_once(
                    lambda dt: self._set_task_status(
                        taskid, "下载中"
                    ), 0
                )

                download_dash(
                    option["video_url"],
                    option["audio_url"],
                    video_path,
                    audio_path,
                    progress=progress,
                )

                Clock.schedule_once(
                    lambda dt: self._set_task_status(
                        taskid, "合并中"
                    ), 0
                )

                # 合并失败时保留独立音视频文件，不将它们冒充完整 MP4。
                try:
                    merge_mp4(video_path, audio_path, output_path)
                except Exception as merge_error:
                    raise RuntimeError(
                        "视频和音频已分别下载，但合并失败。\n"
                        f"原因：{merge_error}\n\n"
                        f"视频文件：{video_path}\n"
                        f"音频文件：{audio_path}\n\n"
                        "请在 APK 中加入可执行的 Android arm64 FFmpeg，"
                        "再进行合并。"
                    )

                for path in (video_path, audio_path):
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                    except Exception:
                        pass

            else:
                output_path = os.path.join(
                    download_dir, stem + ".mp4"
                )

                download_stream(
                    option["url"],
                    output_path,
                    progress=progress,
                )

            if not os.path.isfile(output_path):
                raise RuntimeError("下载流程结束，但没有找到输出文件。")

            if os.path.getsize(output_path) <= 1024:
                raise RuntimeError("输出文件过小，可能不是有效的视频文件。")

            record = {
                "id": taskid,
                "title": task.get("title", name),
                "bvid": task.get("bvid", ""),
                "cover_path": task.get("cover_path", ""),
                "path": output_path,
                "created": task.get("created", ""),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "size": os.path.getsize(output_path),
                "status": "已完成",
                "option_label": option.get("label", ""),
            }

            Clock.schedule_once(
                lambda dt, rec=record:
                self._download_finished_ok(taskid, rec),
                0
            )

        except Exception as e:
            Clock.schedule_once(
                lambda dt, msg=str(e):
                self._download_finished_error(taskid, msg),
                0
            )

    def _download_progress(self, taskid, percent):
        task = self._find_task(taskid)
        if not task:
            return

        task["percent"] = percent

        # 降低 UI 刷新频率，避免下载时反复重建整个列表。
        if self.page_name == "home":
            self.show_home()

    def _set_task_status(self, taskid, status):
        task = self._find_task(taskid)
        if task:
            task["status"] = status
            self.show_home()

    def _download_finished_ok(self, taskid, record):
        self.busy = False

        task = self._find_task(taskid)
        if task:
            task.update(record)
            task["percent"] = 100
            task["status"] = "已完成"

        self.history = [
            item for item in self.history
            if item.get("id") != taskid
        ]
        self.history.insert(0, record)
        self._save_history()

        self.show_home()
        self._popup(
            "下载完成",
            f"{record['title']}\n\n"
            f"保存位置：\n{record['path']}\n\n"
            f"文件大小：{human_size(record.get('size', 0))}"
        )

    def _download_finished_error(self, taskid, message):
        self.busy = False

        task = self._find_task(taskid)
        if task:
            task.update({
                "status": "已失败",
                "error": str(message),
            })

        self.show_home()
        self._popup("下载失败", str(message))

    # ---------------------------------------------------------
    # 我的 / 已下载 / 导出
    # ---------------------------------------------------------

    def show_mine(self):
        self.page_name = "mine"
        self._scroll()
        self._nav()

        self.content.add_widget(self._label(
            "我的 BiliPink",
            23, PINK, True, height=dp(48)
        ))
        self.content.add_widget(self._label(
            f"已完成 {len(self.history)} 个下载任务",
            13, MUTED, height=dp(30)
        ))

        self.content.add_widget(self._btn(
            "刷新列表",
            self.show_mine,
            PINK_LIGHT,
            PINK,
        ))

        self.content.add_widget(self._label(
            "已下载文件",
            16, TEXT, True, height=dp(38)
        ))

        if not self.history:
            self.content.add_widget(self._label(
                "这里还没有下载完成的视频。",
                13, MUTED, height=dp(70)
            ))

        for rec in self.history:
            card = Surface(
                orientation="vertical",
                size_hint_y=None,
                height=dp(145),
                padding=dp(12),
                spacing=dp(5),
            )

            card.add_widget(self._label(
                rec.get("title", "未命名视频"),
                14, PINK, True, height=dp(34)
            ))
            card.add_widget(self._label(
                f"{rec.get('option_label', '')}  ·  "
                f"{human_size(rec.get('size', 0))}",
                12, MUTED, height=dp(24)
            ))

            path = rec.get("path", "")
            exists = os.path.isfile(path)
            card.add_widget(self._label(
                "文件存在" if exists else "文件已不存在",
                12, GREEN if exists else RED,
                height=dp(22)
            ))

            actions = BoxLayout(
                size_hint_y=None,
                height=dp(36),
                spacing=dp(8),
            )
            actions.add_widget(self._btn(
                "导出到下载目录",
                lambda r=rec: self._export_record(r),
                PINK, WHITE, dp(36), True
            ))
            actions.add_widget(self._btn(
                "删除记录",
                lambda r=rec: self._delete_record(r),
                PINK_LIGHT, PINK, dp(36)
            ))
            card.add_widget(actions)
            self.content.add_widget(card)

        self.content.add_widget(self._btn(
            "清空下载记录",
            self._clear_history_confirm,
            WHITE, RED,
        ))

    def _export_record(self, record):
        src = record.get("path", "")

        if not src or not os.path.isfile(src):
            self._popup("导出失败", "原文件不存在，可能已被删除。")
            return

        try:
            # Android 11+ 可能限制直接写入公共目录；
            # 若系统拒绝访问，会显示错误而不会谎报成功。
            if platform == "android":
                dest_dir = "/storage/emulated/0/Download/BiliPink"
            else:
                dest_dir = os.path.join(
                    os.path.expanduser("~"), "Downloads", "BiliPink"
                )

            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(src))
            shutil.copy2(src, dest)

            self._popup(
                "导出完成",
                f"已复制到：\n{dest}"
            )

        except Exception as e:
            self._popup(
                "导出失败",
                "系统可能限制了 APK 写入公共下载目录。\n\n"
                f"详细原因：{e}\n\n"
                "原文件仍保存在应用内部下载目录中。"
            )

    def _delete_record(self, record):
        self.history = [
            x for x in self.history
            if x.get("id") != record.get("id")
        ]
        self._save_history()
        self.show_mine()

    def _clear_history_confirm(self):
        box = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(14),
        )
        box.add_widget(self._label(
            "只清除下载记录，不会删除已经下载的视频文件。",
            14, TEXT, height=dp(64)
        ))

        popup = Popup(
            title="清除记录",
            content=box,
            size_hint=(0.86, 0.34),
        )

        row = BoxLayout(
            size_hint_y=None,
            height=dp(42),
            spacing=dp(10),
        )
        row.add_widget(self._btn(
            "取消", popup.dismiss, WHITE, MUTED
        ))

        def clear():
            self.history = []
            self._save_history()
            popup.dismiss()
            self.show_mine()

        row.add_widget(self._btn(
            "确认清除", clear, PINK, WHITE, bold=True
        ))
        box.add_widget(row)
        popup.open()

    # ---------------------------------------------------------
    # 本地历史记录
    # ---------------------------------------------------------

    def _history_path(self):
        return os.path.join(self.user_data_dir, "history.json")

    def _save_history(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)

            with open(
                self._history_path(),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    self.history,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    def _load_history(self):
        try:
            with open(
                self._history_path(),
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            if isinstance(data, list):
                self.history = [
                    x for x in data
                    if isinstance(x, dict)
                ]
        except (OSError, ValueError, TypeError):
            self.history = []

    # ---------------------------------------------------------
    # 弹窗
    # ---------------------------------------------------------

    def _popup(self, title, message):
        box = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(14),
        )

        msg = self._label(
            message,
            13, TEXT, height=dp(150)
        )
        msg.text_size = (Window.width * 0.76, None)
        box.add_widget(msg)

        popup = Popup(
            title=str(title),
            content=box,
            size_hint=(0.88, 0.48),
            auto_dismiss=True,
        )
        box.add_widget(self._btn(
            "知道了", popup.dismiss, PINK, WHITE, bold=True
        ))
        popup.open()


    def on_start(self):
        self._load_history()
        self.show_home()


if __name__ == "__main__":
    BiliPinkApp().run()
 
