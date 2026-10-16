# -*- coding: utf-8 -*-
"""BiliPink v2.4.0 | Kivy Android | Search Keyword Support"""
import json, os, shutil, threading, urllib.request, time, hashlib
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

WBI_IMG_KEY = "337536b025854e6c8752557253147eb5"
WBI_SUB_KEY = "73278d948d84fd84097d6129478c9012"
BUVID = "abcdef1234567890abcdef1234567890"
UA = "Mozilla/5.0 (Android; Mobile) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36"


def fmt_num(n):
    try:
        n = int(n or 0)
        if n >= 100000000:
            return f'{n / 100000000:.1f}亿'
        if n >= 10000:
            return f'{n / 10000:.1f}万'
        return str(n)
    except Exception:
        return str(n or 0)


def fmt_time(n):
    try:
        n = int(n)
        if n >= 3600:
            return f'{n // 3600:02d}:{n % 3600 // 60:02d}:{n % 60:02d}'
        else:
            return f'{n // 60:02d}:{n % 60:02d}'
    except Exception:
        return '--:--'


def human_size(n):
    try:
        n = float(n)
        unit_list = ('B', 'KB', 'MB', 'GB')
        for u in unit_list:
            if n < 1024 or u == 'GB':
                return f'{n:.1f} {u}'
            n /= 1024
    except Exception:
        return '未知大小'


def enc_wbi(params: dict, img_key: str, sub_key: str):
    table = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,6,51,17,26,34,22,52,21,20,25,4,30]
    def mix(s): return "".join([s[i] for i in table if i < len(s)])
    salt = mix(img_key + sub_key)
    params["wts"] = str(int(time.time()))
    items = sorted(params.items())
    qs = "&".join(f"{k}={v}" for k, v in items)
    params["w_rid"] = hashlib.md5((qs + salt).encode()).hexdigest()
    return params


class Surface(BoxLayout):
    def __init__(self, bg=WHITE, radius=dp(16), **kwargs):
        super().__init__(**kwargs)
        self._bg = bg
        self._radius = radius
        with self.canvas.before:
            Color(0.0, 0.0, 0.0, 0.075)
            self.shadow_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*bg)
            self.main_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._draw_update, size=self._draw_update)

    def _draw_update(self, *args):
        self.shadow_rect.pos = (self.x, self.y - dp(2))
        self.shadow_rect.size = self.size
        self.main_rect.pos = self.pos
        self.main_rect.size = self.size


class BiliPinkApp(App):
    title = 'BiliPink'

    def _extract_asset_to_file(self, asset_fullpath, dest_path):
        if platform != 'android':
            local_p = os.path.abspath(asset_fullpath)
            if os.path.isfile(local_p):
                return local_p
            return None
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
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
            with open(dest_path, "wb") as f:
                f.write(buffer)
            return dest_path
        except Exception:
            return None

    def _load_cjk_font_safe(self, dt):
        global FONT, _FONT_LOADED
        if _FONT_LOADED:
            return
        try:
            from android.storage import app_storage_path
            cache_font_path = os.path.join(app_storage_path(), "NotoSansSC-Regular.otf")
            if os.path.isfile(cache_font_path):
                fp = cache_font_path
            else:
                fp = self._extract_asset_to_file("fonts/NotoSansSC-Regular.otf", cache_font_path)
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
                if self.page_name == 'home':
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
            if platform != 'android':
                return os.path.abspath("fonts/avatar-reference.jpg")
            from android.storage import app_storage_path
            cache_ava = os.path.join(app_storage_path(), "avatar-reference.jpg")
            if os.path.isfile(cache_ava):
                return cache_ava
            return self._extract_asset_to_file("fonts/avatar-reference.jpg", cache_ava)
        except Exception:
            return None

    def on_start(self):
        self._load_history()

    def build(self):
        Window.clearcolor = BG
        self.busy = False
        self.current_info = None
        self.current_options = []
        self.history = []
        self.tasks = []
        self.filter = '全部'
        self.page_name = 'home'
        self.search_result_list = []

        self.root_layout = BoxLayout(orientation='vertical', spacing=0)
        self.body = BoxLayout(orientation='vertical')
        self.root_layout.add_widget(self.body)
        self.nav = BoxLayout(size_hint_y=None, height=dp(66),
                             padding=[dp(36), dp(5), dp(36), dp(4)], spacing=dp(65))
        self.root_layout.add_widget(self.nav)

        self.show_home()
        Clock.schedule_once(self._load_cjk_font_safe, 0.12)
        return self.root_layout

    def _label(self, text, size=14, color=TEXT, bold=False, halign='left', height=None):
        h = height or max(24, size * 1.75)
        use_font = FONT if FONT is not None else "Roboto"
        w = Label(
            text=str(text),
            font_name=use_font,
            font_size=dp(size),
            color=color,
            bold=bold,
            halign=halign,
            valign='middle',
            size_hint_y=None,
            height=dp(h)
        )
        w.bind(size=lambda obj, *x: setattr(obj, 'text_size', (obj.width, None)))
        return w

    def _btn(self, text, cb, color=WHITE, fg=TEXT, height=dp(44), bold=False):
        use_font = FONT if FONT is not None else "Roboto"
        b = Button(
            text=text,
            font_name=use_font,
            font_size=dp(14),
            bold=bold,
            background_normal='',
            background_down='',
            background_color=color,
            color=fg,
            size_hint_y=None,
            height=height
        )
        b.bind(on_release=lambda *a: cb())
        return b

    def _scroll(self):
        self.body.clear_widgets()
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(2), scroll_type=['bars', 'content'])
        self.content = BoxLayout(orientation='vertical', size_hint_y=None,
                                 spacing=dp(13), padding=[dp(17), dp(10), dp(17), dp(15)])
        self.content.bind(minimum_height=self.content.setter('height'))
        self.scroll.add_widget(self.content)
        self.body.add_widget(self.scroll)

    def _nav(self):
        self.nav.clear_widgets()

        def goto(page):
            if page == 'home':
                self.show_home()
            else:
                self.show_mine()

        for key, label, icon in (('home', '主页', ''), ('mine', '我的', '')):
            active = self.page_name == key
            c = PINK if active else (0.48, 0.48, 0.49, 1)
            box = BoxLayout(orientation='vertical', spacing=0)
            btn = Button(text=icon, font_name=FONT if FONT else "Roboto", font_size=dp(29),
                         background_normal='', background_color=(0, 0, 0, 0),
                         color=c, size_hint_y=0.62)
            cap = Label(text=label, font_name=FONT if FONT else "Roboto", font_size=dp(12), color=c, size_hint_y=0.38)
            btn.bind(on_release=lambda *a, k=key: goto(k))
            cap.bind(on_touch_down=lambda inst, touch, k=key: goto(k) if inst.collide_point(*touch.pos) else None)
            box.add_widget(btn)
            box.add_widget(cap)
            self.nav.add_widget(box)

    def _search_draw(self, w):
        self.search_bg.pos = w.pos
        self.search_bg.size = w.size
        self.search_line.rounded_rectangle = (w.x, w.y, w.width, w.height, dp(25))

    def _move_line(self, w):
        if hasattr(w, '_line'):
            w._line.pos = w.pos
            w._line.size = w.size

    def set_filter(self, val):
        self.filter = val
        self.show_home()

    def show_home(self):
        self.page_name = 'home'
        self._scroll()
        self._nav()
        top = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(10))

        ava_p = self._load_avatar()
        if ava_p and os.path.isfile(ava_p):
            avatar = Image(source=ava_p, fit_mode='contain', size_hint_x=None, width=dp(48))
        else:
            avatar = Label(text='', font_name=FONT if FONT else "Roboto", font_size=dp(33), color=PINK, size_hint_x=None, width=dp(42))
        top.add_widget(avatar)

        search_wrap = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(12), dp(1)], spacing=dp(5))
        with search_wrap.canvas.before:
            Color(1,1,1,1)
            self.search_bg = RoundedRectangle(pos=search_wrap.pos, size=search_wrap.size, radius=[dp(25)])
            Color(0.48,0.48,0.49,1)
            self.search_line = Line(rounded_rectangle=(search_wrap.x,search_wrap.y,search_wrap.width,search_wrap.height,dp(25)), width=1.1)
        search_wrap.bind(pos=self._search_draw, size=self._search_draw)

        search_icon = Button(text='', font_name=FONT if FONT else "Roboto", font_size=dp(27),
                             background_normal='', background_color=(0,0,0,0),
                             color=(0.43,0.43,0.44,1), size_hint_x=None, width=dp(32))
        search_icon.bind(on_release=lambda *x:self.do_search_or_parse())
        self.search_input = TextInput(
            hint_text='输入BV/AV/链接/关键词',
            font_name=FONT if FONT else "Roboto",
            font_size=dp(16),
            multiline=False,
            background_normal='',
            background_active='',
            background_color=(0,0,0,0),
            foreground_color=TEXT,
            hint_text_color=(0.48,0.48,0.49,1),
            cursor_color=PINK,
            padding=[dp(3), dp(10)]
        )
        self.search_input.bind(on_text_validate=lambda *x:self.do_search_or_parse())
        search_wrap.add_widget(search_icon)
        search_wrap.add_widget(self.search_input)
        top.add_widget(search_wrap)
        self.content.add_widget(top)

        filters = BoxLayout(size_hint_y=None, height=dp(43), spacing=dp(6))
        for fnam in ('全部','已完成','进行中','已失败'):
            col = PINK if self.filter == fnam else MUTED
            cell = BoxLayout(orientation='vertical', spacing=0)
            b = Button(text=fnam, font_name=FONT if FONT else "Roboto", font_size=dp(14),
                       background_normal='', background_color=(0,0,0,0), color=col)
            b.bind(on_release=lambda *x, v=fnam:self.set_filter(v))
            cell.add_widget(b)
            underline = Widget(size_hint_y=None, height=dp(3))
            with underline.canvas:
                Color(*(PINK if self.filter == fnam else (1,1,1,0)))
                underline._line = RoundedRectangle(pos=underline.pos, size=underline.size, radius=[dp(2)])
            underline.bind(pos=self._move_line, size=self._move_line)
            cell.add_widget(underline)
            filters.add_widget(cell)
        self.content.add_widget(filters)

        if self.search_result_list:
            self.content.add_widget(self._label("搜索结果",15,TEXT,True,'left',dp(36)))
            for item in self.search_result_list:
                self.content.add_widget(self._search_result_card(item))

        if self.filter == '全部' and not self.tasks and not self.history and not self.search_result_list:
            self.content.add_widget(self._label('输入BV / AV / 链接或者中文关键词开始',13,MUTED,False,'center',dp(90)))

        visible = []
        for tsk in self.tasks:
            s = tsk.get('status','')
            if self.filter == '全部' \
                    or (self.filter == '已完成' and s == '已完成') \
                    or (self.filter == '进行中' and s in ('解析中','下载中','等待下载')) \
                    or (self.filter == '已失败' and s == '已失败'):
                visible.append(tsk)
        if self.filter in ('全部','已完成'):
            for hrec in self.history:
                if not any(t.get('id') == hrec.get('id') for t in visible):
                    visible.append({**hrec, 'status':'已完成'})
        visible.sort(key=lambda x:x.get('created',''), reverse=True)
        for item in visible:
            self.content.add_widget(self._task_card(item))

    def _search_result_card(self, it):
        card = Surface(orientation='horizontal', size_hint_y=None, height=dp(104), padding=0, spacing=0)
        thumb = BoxLayout(size_hint_x=None, width=dp(112))
        cover_path = ''
        cache_dir = os.path.join(self.user_data_dir, 'covers')
        os.makedirs(cache_dir, exist_ok=True)
        local_cover = os.path.join(cache_dir, it["bvid"] + "_s.jpg")
        if os.path.exists(local_cover):
            thumb.add_widget(Image(source=local_cover, fit_mode='cover'))
        else:
            pl = FloatLayout()
            with pl.canvas.before:
                Color(0.92,0.91,0.91,1)
                pl.bg = RoundedRectangle(pos=pl.pos, size=pl.size, radius=[dp(12)])
            pl.bind(pos=lambda w,*_:setattr(pl.bg,'pos',w.pos), size=lambda w,*_:setattr(pl.bg,'size',w.size))
            pl.add_widget(Label(text='', font_name=FONT if FONT else "Roboto", font_size=dp(14), bold=True, color=PINK))
            thumb.add_widget(pl)
        card.add_widget(thumb)
        info = BoxLayout(orientation='vertical', padding=[dp(12), dp(7), dp(10), dp(5)], spacing=dp(2))
        info.add_widget(self._label(it["title"],14,PINK,True,height=dp(34)))
        sub = f"{it['duration']} | {it['pubdate']} | UP:{it['author']}"
        info.add_widget(self._label(sub,11,MUTED,height=dp(21)))
        row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
        row.add_widget(self._btn("选择解析", lambda bv=it["bvid"]: self.parse_by_bvid(bv), PINK, WHITE, dp(36), True))
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
        has_link = "bilibili.com" in txt or "b23.tv" in txt
        if has_bv or has_av or has_link:
            self.search_result_list.clear()
            self.parse_video()
        else:
            if self.busy:
                return
            self.busy = True
            threading.Thread(target=self._search_worker, args=(txt,), daemon=True).start()

    def _search_worker(self, kw):
        res = bilibili_search(kw)
        Clock.schedule_once(lambda dt: self._search_done(res),0)

    def _search_done(self, res):
        self.busy = False
        self.search_result_list = res
        self.show_home()

    def _task_card(self, t):
        card = Surface(orientation='horizontal', size_hint_y=None, height=dp(100), padding=0, spacing=0)
        thumb = BoxLayout(size_hint_x=None, width=dp(112))
        cover = t.get('cover_path','')
        if cover and os.path.isfile(cover):
            thumb.add_widget(Image(source=cover, fit_mode='cover'))
        else:
            pl = FloatLayout()
            with pl.canvas.before:
                Color(0.92,0.91,0.91,1)
                pl.bg = RoundedRectangle(pos=pl.pos, size=pl.size, radius=[dp(12)])
            pl.bind(pos=lambda w,*_:setattr(pl.bg,'pos',w.pos), size=lambda w,*_:setattr(pl.bg,'size',w.size))
            pl.add_widget(Label(text='', font_name=FONT if FONT else "Roboto", font_size=dp(14), bold=True, color=PINK))
            thumb.add_widget(pl)
        card.add_widget(thumb)
        info = BoxLayout(orientation='vertical', padding=[dp(12), dp(7), dp(10), dp(5)], spacing=dp(2))
        title = t.get('title','正在解析视频…')
        info.add_widget(self._label(title,14,PINK,True,height=dp(36)))
        subtext = t.get('time') or t.get('created') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        info.add_widget(self._label(subtext,11,MUTED,height=dp(21)))
        row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(5))
        stat = t.get('status','已完成')
        stat_color = GREEN if stat == '已完成' else (RED if stat == '已失败' else PINK)
        stat_text = '' if stat == '已完成' else (' ' if stat == '已失败' else ' ')
        row.add_widget(self._label(stat_text+stat,12,stat_color,True,height=dp(24)))
        if stat in ('下载中','解析中','等待下载'):
            row.add_widget(self._label(f"{t.get('percent',0):.0f}%",11,MUTED,False,'right',dp(24)))
        info.add_widget(row)
        if stat in ('下载中','解析中','等待下载'):
            pb = ProgressBar(max=100, value=t.get('percent',0), size_hint_y=None, height=dp(4))
            info.add_widget(pb)
        card.add_widget(info)
        card.bind(on_touch_down=lambda w,touch,task=t:self._show_task(task) if w.collide_point(*touch.pos) else None)
        return card

    def _show_task(self,t):
        if t.get('path') and os.path.isfile(t['path']):
            self._popup('下载任务',f"{t.get('title','视频')}\n\n状态：{t.get('status','已完成')}\n文件：{t.get('path','')}\n大小：{human_size(os.path.getsize(t['path']))}")
        elif t.get('error'):
            self._popup('任务失败',t['error'])
        else:
            self._popup('下载任务',f"{t.get('title','视频')}\n状态：{t.get('status','处理中')}")

    def parse_video(self):
        if self.busy:
            self._popup('请稍候','当前已有解析或下载任务，请稍候。')
            return
        raw = self.search_input.text.strip()
        if not raw:
            self._popup('输入视频链接','请粘贴B站视频链接，或输入BV / AV号。')
            return
        self.busy = True
        tid = str(datetime.now().timestamp())
        newtsk = {'id':tid,'title':'正在解析视频…','status':'解析中','created':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'percent':0}
        self.tasks.insert(0, newtsk)
        self.show_home()
        threading.Thread(target=self._parse_worker, args=(raw, tid), daemon=True).start()

    def _parse_worker(self, raw, taskid):
        try:
            info = get_video_info(raw)
            options = get_download_options(info, '')
            cover_path = ''
            try:
                cache_dir = os.path.join(self.user_data_dir, 'covers')
                os.makedirs(cache_dir, exist_ok=True)
                cover_path = os.path.join(cache_dir, info['bvid']+'.jpg')
                if not os.path.isfile(cover_path):
                    req = urllib.request.Request(info['cover'], headers={'User-Agent':UA,'Referer':'https://www.bilibili.com/'})
                    with urllib.request.urlopen(req, timeout=15) as r, open(cover_path,'wb') as f:
                        f.write(r.read())
            except Exception:
                cover_path = ''
            Clock.schedule_once(lambda dt:self._parsed(taskid, info, options, cover_path),0)
        except Exception as e:
            Clock.schedule_once(lambda dt, msg=str(e):self._parse_error(taskid, msg),0)

    def _find_task(self, tid):
        return next((x for x in self.tasks if x.get('id') == tid), None)

    def _parsed(self, taskid, info, options, cover_path):
        self.busy = False
        self.current_info = info
        self.current_options = options
        t = self._find_task(taskid)
        if t:
            t.update({'title':info['title'],'cover_path':cover_path,'status':'等待下载','info':info,'options':options})
        self.show_home()
        self._quality_popup(info, options, taskid)

    def _parse_error(self, taskid, msg):
        self.busy = False
        t = self._find_task(taskid)
        if t:
            t.update({'title':'解析失败','status':'已失败','error':msg})
        self.show_home()
        self._popup('解析失败', msg[:900])

    def _quality_popup(self, info, options, taskid):
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(8))
        box.add_widget(self._label(info['title'],16,PINK,True,height=dp(48)))
        box.add_widget(self._label(f"UP主：{info['owner']}  ·  时长：{fmt_time(info['duration'])}\n播放 {fmt_num(info['view'])}  ·  弹幕 {fmt_num(info['danmaku'])}  ·  评论 {fmt_num(info['reply'])}",12,MUTED,height=dp(48)))
        box.add_widget(self._label('选择可用画质',13,TEXT,True,height=dp(28)))
        sel = {'opt': options[0]}
        for opt in options[:8]:
            box.add_widget(self._btn(f"{opt['label']} · {human_size(opt.get('size',0))}", lambda o=opt: sel.update(opt=o), PINK_LIGHT, PINK, dp(38), True))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        pop = Popup(title='视频解析成功', content=box, size_hint=(0.92,0.83), auto_dismiss=True)
        row.add_widget(self._btn('取消', pop.dismiss, PINK_LIGHT, PINK))
        row.add_widget(self._btn('开始下载', lambda:(pop.dismiss(), self._start_task_download(taskid, sel['opt'])), PINK, WHITE, dp(44), True))
        box.add_widget(row)
        pop.open()

    def _start_task_download(self, taskid, option):
        if self.busy:
            self._popup('请稍候','当前有任务正在下载。')
            return
        t = self._find_task(taskid)
        if not t:
            return
        self.busy = True
        t.update({'status':'下载中','percent':0,'quality':option['label']})
        self.show_home()
        threading.Thread(target=self._download_worker, args=(taskid, option), daemon=True).start()

    def _download_worker(self, taskid, option):
        t = self._find_task(taskid)
        info = (t or {}).get('info') or self.current_info
        try:
            outdir = os.path.join(self.user_data_dir, 'downloads')
            os.makedirs(outdir, exist_ok=True)
            fn = safe_filename(info['title'])
            savepath = os.path.join(outdir, f"{fn}_{info['bvid']}_{safe_filename(option['label'])}.mp4")
            def prog(done, total):
                pct = done * 100.0 / total if total else 0
                Clock.schedule_once(lambda dt,d=done,tot=total,pc=pct:self._progress_task(taskid,d,tot,pc),0)
            saved = download_stream(option['url'], savepath, prog)
            rec = {'id':taskid,'title':info['title'],'path':saved,'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   'quality':option['label'],'bvid':info['bvid'],'cover_path':(t or {}).get('cover_path',''),'status':'已完成','percent':100,'created':(t or {}).get('created','')}
            Clock.schedule_once(lambda dt,r=rec:self._download_done(taskid,r),0)
        except Exception as e:
            Clock.schedule_once(lambda dt,msg=str(e):self._download_error(taskid,msg),0)

    def _progress_task(self, tid, done, total, p):
        t = self._find_task(tid)
        if t:
            t['percent'] = p
            t['bytes'] = done
            t['total'] = total
            last = int(t.get('_last_refresh_percent', -5))
            if int(p) >= last +5 or p >=99.9:
                t['_last_refresh_percent'] = int(p)
                if self.page_name == 'home':
                    self.show_home()

    def _download_done(self, tid, rec):
        self.busy = False
        t = self._find_task(tid)
        if t:
            t.update(rec)
        self.history = [h for h in self.history if h.get('id') != tid]
        self.history.insert(0, rec)
        self._save_history()
        self.show_home()
        self._popup('下载完成',f"{rec['title']}\n画质：{rec['quality']}\n文件保存在应用私有目录\n{rec['path']}\n可前往「我的 → 已下载文件」导出")

    def _download_error(self, tid, msg):
        self.busy = False
        t = self._find_task(tid)
        if t:
            t.update({'status':'已失败','error':msg})
        self.show_home()
        self._popup('下载失败', msg[:900])

    def show_mine(self):
        self.page_name = 'mine'
        self._scroll()
        self._nav()
        ava_p = self._load_avatar()
        profile = Surface(orientation='horizontal', size_hint_y=None, height=dp(102), padding=dp(14), spacing=dp(12))
        if ava_p and os.path.isfile(ava_p):
            profile.add_widget(Image(source=ava_p, fit_mode='contain', size_hint_x=None, width=dp(105)))
        else:
            profile.add_widget(Label(text='', font_name=FONT if FONT else "Roboto", font_size=dp(56), color=PINK, size_hint_x=None, width=dp(105)))
        col = BoxLayout(orientation='vertical', spacing=dp(4))
        col.add_widget(self._label('未登录',18,PINK,True,height=dp(35)))
        col.add_widget(self._label('点击此处登录',14,MUTED,height=dp(28)))
        profile.add_widget(col)
        profile.bind(on_touch_down=lambda w,t: self._login_info() if w.collide_point(*t.pos) else None)
        self.content.add_widget(profile)

        menu = Surface(orientation='vertical', size_hint_y=None, padding=0, spacing=0)
        rows = [('代码仓库','',lambda:self._open_url('https://github.com/')),
                ('当前版本','2.4.0',None),
                ('开源组件许可','',self.show_licenses),
                ('问题反馈','',self.feedback)]
        for idx,(title,val,cb) in enumerate(rows):
            r = BoxLayout(size_hint_y=None, height=dp(57), padding=[dp(15),0,dp(15),0])
            r.add_widget(self._label(title,15,(0.43,0.42,0.44,1),False,height=dp(56)))
            r.add_widget(self._label(val,15,PINK if title=='当前版本' else MUTED, title=='当前版本','right',dp(56)))
            if cb:
                r.bind(on_touch_down=lambda w,t,f=cb: f() if w.collide_point(*t.pos) else None)
            menu.add_widget(r)
            if idx < len(rows)-1:
                with menu.canvas.after:
                    Color(*BORDER)
                    Line(points=[menu.x, menu.y, menu.x+menu.width, menu.y], width=0.7)
        self.content.add_widget(menu)

        actions = [('设置',self.settings,False),
                   ('给我们评分',self.rate_app,False),
                   ('已下载文件',self.show_downloaded,False),
                   ('清除数据',self.clear_data,True)]
        for title, cb, is_red in actions:
            r = Surface(orientation='horizontal', size_hint_y=None, height=dp(58), padding=[dp(15),0,dp(15),0])
            tc = RED if is_red else (0.43,0.42,0.44,1)
            r.add_widget(self._label(title,15,tc,False,height=dp(55)))
            r.add_widget(self._label('',30,MUTED,False,'right',dp(55)))
            r.bind(on_touch_down=lambda w,t,f=cb: f() if w.collide_point(*t.pos) else None)
            self.content.add_widget(r)

    def _login_info(self):
        self._popup('账号登录','当前版本暂未实现官方账号登录。需要高画质时，后续版本支持手动填入Cookie。')

    def settings(self):
        self._popup('设置','BiliPink 设置\n语言：简体中文\n主题：粉色白色\n下载目录：应用私有目录\n文件名：保留中文标题\n提示：DASH音视频暂不支持合并。')

    def show_licenses(self):
        self._popup('开源组件许可','BiliPink 使用 Kivy；字体 Noto Sans CJK；其他组件遵循各自许可证。')

    def feedback(self):
        self._popup('问题反馈','反馈请带上：视频链接类型、报错文字、Android版本。')

    def rate_app(self):
        self._popup('感谢支持','项目尚未上架商店，暂时无法评分。')

    def show_downloaded(self):
        self.page_name = 'mine'
        self._scroll()
        self._nav()
        self.content.add_widget(self._label('已下载文件',20,PINK,True,height=dp(38)))
        self.content.add_widget(self._label('视频保存在应用私有目录，点击导出复制到Download/BiliPink',12,MUTED,height=dp(48)))
        if not self.history:
            self.content.add_widget(self._label('暂时没有已下载文件',14,MUTED,False,'center',dp(70)))
        else:
            for rec in self.history:
                card = Surface(orientation='vertical', size_hint_y=None, padding=dp(12), spacing=dp(6))
                card.add_widget(self._label(rec.get('title','视频'),14,PINK,True,height=dp(38)))
                card.add_widget(self._label(f"{rec.get('quality','')} · {rec.get('time','')}",11,MUTED,height=dp(42)))
                row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
                row.add_widget(self._btn('导出到手机',lambda r=rec:self.export_record(r), PINK, WHITE, dp(40), True))
                row.add_widget(self._btn('删除记录',lambda r=rec:self.delete_record(r), PINK_LIGHT, PINK, dp(40)))
                card.add_widget(row)
                self.content.add_widget(card)
        self.content.add_widget(self._btn('返回我的', self.show_mine, PINK_LIGHT, PINK))

    def export_record(self, rec):
        src = rec.get('path','')
        if not src or not os.path.isfile(src):
            self._popup('文件不存在','原文件已移动或删除。')
            return
        tr
