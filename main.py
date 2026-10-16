# -*- coding: utf-8 -*-
"""BiliPink Android client. UTF-8 source and bundled CJK font are used for Chinese text."""
import json, os, shutil, threading, urllib.request
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

from bili_api import get_video_info, get_download_options
from downloader import download_stream, safe_filename

PINK=(0.91,0.39,0.57,1); PINK_LIGHT=(1.0,0.91,0.95,1); WHITE=(1,1,1,1)
BG=(1,1,1,1); TEXT=(0.31,0.30,0.32,1); MUTED=(0.52,0.51,0.53,1); GREEN=(0.30,0.66,0.40,1); RED=(0.82,0.25,0.30,1); BORDER=(0.90,0.89,0.90,1)
FONT='Roboto'

def fmt_num(n):
    try:
        n=int(n or 0)
        if n>=100000000: return f'{n/100000000:.1f}亿'
        if n>=10000: return f'{n/10000:.1f}万'
        return str(n)
    except Exception: return str(n or 0)
def fmt_time(n):
    try:
        n=int(n); return f'{n//3600:02d}:{n%3600//60:02d}:{n%60:02d}' if n>=3600 else f'{n//60:02d}:{n%60:02d}'
    except Exception: return '--:--'
def human_size(n):
    try:
        n=float(n)
        for unit in ('B','KB','MB','GB'):
            if n<1024 or unit=='GB': return f'{n:.1f} {unit}'
            n/=1024
    except Exception: return '未知大小'

class Surface(BoxLayout):
    def __init__(self, bg=WHITE, radius=dp(16), **kwargs):
        super().__init__(**kwargs); self.padding=dp(1)
        self._bg=bg; self._radius=radius
        with self.canvas.before:
            Color(0.0,0.0,0.0,0.075); self.shadow=RoundedRectangle(pos=(self.x,self.y-dp(2)),size=self.size,radius=[radius])
            Color(*bg); self.rect=RoundedRectangle(pos=self.pos,size=self.size,radius=[radius])
        self.bind(pos=self._draw,size=self._draw)
    def _draw(self,*_):
        self.shadow.pos=(self.x,self.y-dp(2)); self.shadow.size=self.size; self.rect.pos=self.pos; self.rect.size=self.size

class BiliPinkApp(App):
    title='BiliPink'
    def build(self):
        Window.clearcolor=BG
        font_path=os.path.join(os.path.dirname(__file__),'assets','NotoSansSC-Regular.otf')
        if os.path.isfile(font_path):
            try: LabelBase.register(name='BiliCJK',fn_regular=font_path,fn_bold=font_path,fn_italic=font_path,fn_bolditalic=font_path); global FONT; FONT='BiliCJK'
            except Exception: pass
        self.busy=False; self.current_info=None; self.current_options=[]; self.current_cookie=''; self.history=[]; self.tasks=[]; self.filter='全部'; self.page_name='home'
        self.root_layout=BoxLayout(orientation='vertical',spacing=0)
        self.body=BoxLayout(orientation='vertical')
        self.root_layout.add_widget(self.body)
        self.nav=BoxLayout(size_hint_y=None,height=dp(66),padding=[dp(36),dp(5),dp(36),dp(4)],spacing=dp(65))
        self.root_layout.add_widget(self.nav)
        self._load_history(); self.show_home(); return self.root_layout
    def _label(self,text,size=14,color=TEXT,bold=False,halign='left',height=None):
        w=Label(text=str(text),font_name=FONT,font_size=f'{size}sp',color=color,bold=bold,halign=halign,valign='middle',size_hint_y=None,height=dp(height or max(24,size*1.8)))
        w.bind(size=lambda obj,*_:setattr(obj,'text_size',(obj.width,None)))
        return w
    def _btn(self,text,cb,color=WHITE,fg=TEXT,height=dp(44),bold=False):
        b=Button(text=text,font_name=FONT,font_size='14sp',bold=bold,background_normal='',background_down='',background_color=color,color=fg,size_hint_y=None,height=height)
        b.bind(on_release=lambda *_:cb()); return b
    def _scroll(self):
        self.body.clear_widgets(); self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(2),scroll_type=['bars','content'])
        self.content=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(13),padding=[dp(17),dp(10),dp(17),dp(15)])
        self.content.bind(minimum_height=self.content.setter('height')); self.scroll.add_widget(self.content); self.body.add_widget(self.scroll)
    def _nav(self):
        self.nav.clear_widgets()
        for key,label,ico in [('home','⌂','主页'),('mine','♙','我的')]:
            active=self.page_name==key; col=PINK if active else (0.48,0.48,0.49,1)
            box=BoxLayout(orientation='vertical',spacing=0)
            btn=Button(text=ico,font_name=FONT,font_size='29sp',background_normal='',background_color=(0,0,0,0),color=col,size_hint_y=.62)
            cap=Label(text=label,font_name=FONT,font_size='12sp',color=col,size_hint_y=.38)
            btn.bind(on_release=lambda *_ ,k=key:self.show_home() if k=='home' else self.show_mine())
            cap.bind(on_touch_down=lambda inst,touch,k=key:self.show_home() if inst.collide_point(*touch.pos) and k=='home' else (self.show_mine() if inst.collide_point(*touch.pos) and k=='mine' else None))
            box.add_widget(btn); box.add_widget(cap); self.nav.add_widget(box)
    def show_home(self):
        self.page_name='home'; self._scroll(); self._nav()
        top=BoxLayout(size_hint_y=None,height=dp(58),spacing=dp(10))
        avatar_path=os.path.join(os.path.dirname(__file__),'assets','avatar-reference.jpg')
        avatar=Image(source=avatar_path,fit_mode='contain',size_hint_x=None,width=dp(48)) if os.path.isfile(avatar_path) else Label(text='▣',font_name=FONT,font_size='33sp',color=PINK,size_hint_x=None,width=dp(42))
        top.add_widget(avatar)
        search_wrap=BoxLayout(size_hint_y=None,height=dp(48),padding=[dp(12),dp(1)],spacing=dp(5))
        with search_wrap.canvas.before:
            Color(1,1,1,1); self.search_bg=RoundedRectangle(pos=search_wrap.pos,size=search_wrap.size,radius=[dp(25)])
            Color(0.48,0.48,0.49,1); self.search_line=Line(rounded_rectangle=(search_wrap.x,search_wrap.y,search_wrap.width,search_wrap.height,dp(25)),width=1.1)
        search_wrap.bind(pos=lambda w,*_:self._search_draw(w),size=lambda w,*_:self._search_draw(w))
        search_icon=Button(text='⌕',font_name=FONT,font_size='27sp',background_normal='',background_color=(0,0,0,0),color=(.43,.43,.44,1),size_hint_x=None,width=dp(32))
        search_icon.bind(on_release=lambda *_:self.parse_video())
        self.search_input=TextInput(hint_text='BV/AV/搜索',font_name=FONT,font_size='16sp',multiline=False,background_normal='',background_active='',background_color=(0,0,0,0),foreground_color=TEXT,hint_text_color=(.48,.48,.49,1),cursor_color=PINK,padding=[dp(3),dp(10)])
        self.search_input.bind(on_text_validate=lambda *_:self.parse_video())
        search_wrap.add_widget(search_icon); search_wrap.add_widget(self.search_input); top.add_widget(search_wrap)
        self.content.add_widget(top)
        filters=BoxLayout(size_hint_y=None,height=dp(43),spacing=dp(6))
        for f in ['全部','已完成','进行中','已失败']:
            col=PINK if self.filter==f else MUTED
            cell=BoxLayout(orientation='vertical',spacing=dp(0))
            b=Button(text=f,font_name=FONT,font_size='14sp',background_normal='',background_color=(0,0,0,0),color=col)
            b.bind(on_release=lambda *_ ,v=f:self.set_filter(v)); cell.add_widget(b)
            underline=Widget(size_hint_y=None,height=dp(3))
            with underline.canvas:
                Color(*(PINK if self.filter==f else (1,1,1,0))); underline._line=RoundedRectangle(pos=underline.pos,size=underline.size,radius=[dp(2)])
            underline.bind(pos=lambda w,*_:self._move_line(w),size=lambda w,*_:self._move_line(w))
            cell.add_widget(underline); filters.add_widget(cell)
        self.content.add_widget(filters)
        if self.filter=='全部' and not self.tasks and not self.history:
            self.content.add_widget(self._label('输入 BV / AV 号或粘贴 B 站视频链接开始解析',13,MUTED,False,'center',dp(90)))
        visible=[]
        for t in self.tasks:
            if self.filter=='全部' or (self.filter=='已完成' and t.get('status')=='已完成') or (self.filter=='进行中' and t.get('status') in ('解析中','下载中','等待下载')) or (self.filter=='已失败' and t.get('status')=='已失败'): visible.append(t)
        if self.filter in ('全部','已完成'):
            for h in self.history:
                if not any(t.get('id')==h.get('id') for t in visible): visible.append({**h,'status':'已完成'})
        visible.sort(key=lambda x:x.get('created',''),reverse=True)
        for task in visible: self.content.add_widget(self._task_card(task))
    def _search_draw(self,w):
        self.search_bg.pos=w.pos; self.search_bg.size=w.size; self.search_line.rounded_rectangle=(w.x,w.y,w.width,w.height,dp(25))
    def _move_line(self,w):
        if hasattr(w,'_line'): w._line.pos=w.pos; w._line.size=w.size
    def set_filter(self,v): self.filter=v; self.show_home()
    def _task_card(self,t):
        card=Surface(orientation='horizontal',size_hint_y=None,height=dp(100),padding=dp(0),spacing=dp(0))
        thumb=BoxLayout(size_hint_x=None,width=dp(112))
        cover=t.get('cover_path')
        if cover and os.path.isfile(cover): thumb.add_widget(Image(source=cover,fit_mode='cover'))
        else:
            placeholder=FloatLayout()
            with placeholder.canvas.before:
                Color(.92,.91,.91,1); placeholder.bg=RoundedRectangle(pos=placeholder.pos,size=placeholder.size)
            placeholder.bind(pos=lambda w,*_:setattr(w.bg,'pos',w.pos),size=lambda w,*_:setattr(w.bg,'size',w.size))
            placeholder.add_widget(Label(text='BiliPink',font_name=FONT,font_size='14sp',bold=True,color=PINK))
            thumb.add_widget(placeholder)
        card.add_widget(thumb)
        info=BoxLayout(orientation='vertical',padding=[dp(12),dp(7),dp(10),dp(5)],spacing=dp(2))
        title=t.get('title','正在解析视频…')
        info.add_widget(self._label(title,14,PINK,True,height=dp(36)))
        sub=t.get('time') or t.get('created') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        info.add_widget(self._label(sub,11,MUTED,height=dp(21)))
        row=BoxLayout(size_hint_y=None,height=dp(24),spacing=dp(5))
        status=t.get('status','已完成'); col=GREEN if status=='已完成' else (RED if status=='已失败' else PINK)
        row.add_widget(self._label(('☁✓' if status=='已完成' else '×' if status=='已失败' else '↓')+' '+status,12,col,True,height=dp(24)))
        if status=='已完成': row.add_widget(self._label('☁✓',22,GREEN,True,'right',dp(24)))
        if status in ('下载中','解析中','等待下载'):
            row.add_widget(self._label(f"{t.get('percent',0):.0f}%",11,MUTED,False,'right',dp(24)))
        info.add_widget(row)
        if status in ('下载中','解析中','等待下载'):
            pb=ProgressBar(max=100,value=t.get('percent',0),size_hint_y=None,height=dp(4)); info.add_widget(pb)
        card.add_widget(info)
        card.bind(on_touch_down=lambda w,touch,task=t: self._show_task(task) if w.collide_point(*touch.pos) else None)
        return card
    def _show_task(self,t):
        if t.get('path') and os.path.isfile(t['path']): self._popup('下载任务',f"{t.get('title','视频')}\n\n状态：{t.get('status','已完成')}\n文件：{t.get('path','')}\n大小：{human_size(os.path.getsize(t['path']))}")
        elif t.get('error'): self._popup('任务失败',t['error'])
        else: self._popup('下载任务',f"{t.get('title','视频')}\n状态：{t.get('status','处理中')}")
    def parse_video(self):
        if self.busy: self._popup('请稍候','当前已有解析或下载任务，请稍候。'); return
        raw=self.search_input.text.strip()
        if not raw: self._popup('输入视频链接','请粘贴 B 站视频链接，或输入 BV / AV 号。'); return
        self.busy=True; task={'id':str(datetime.now().timestamp()),'title':'正在解析视频…','status':'解析中','created':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'percent':0}; self.tasks.insert(0,task); self.show_home()
        threading.Thread(target=self._parse_worker,args=(raw,task['id']),daemon=True).start()
    def _parse_worker(self,raw,taskid):
        try:
            info=get_video_info(raw); options=get_download_options(info,'')
            cover_path=''
            try:
                cache=os.path.join(self.user_data_dir,'covers'); os.makedirs(cache,exist_ok=True); cover_path=os.path.join(cache,info['bvid']+'.jpg')
                if not os.path.isfile(cover_path):
                    req=urllib.request.Request(info['cover'],headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
                    with urllib.request.urlopen(req,timeout=15) as r,open(cover_path,'wb') as f: f.write(r.read())
            except Exception: cover_path=''
            Clock.schedule_once(lambda dt:self._parsed(taskid,info,options,cover_path),0)
        except Exception as e: Clock.schedule_once(lambda dt,msg=str(e):self._parse_error(taskid,msg),0)
    def _parsed(self,taskid,info,options,cover_path):
        self.busy=False; self.current_info=info; self.current_options=options
        task=self._find_task(taskid)
        if task: task.update({'title':info['title'],'cover_path':cover_path,'status':'等待下载','info':info,'options':options})
        self.show_home(); self._quality_popup(info,options,taskid)
    def _find_task(self,taskid): return next((t for t in self.tasks if t.get('id')==taskid),None)
    def _parse_error(self,taskid,msg):
        self.busy=False; t=self._find_task(taskid)
        if t: t.update({'title':'解析失败','status':'已失败','error':msg})
        self.show_home(); self._popup('解析失败',msg[:900])
    def _quality_popup(self,info,options,taskid):
        box=BoxLayout(orientation='vertical',padding=dp(15),spacing=dp(8))
        box.add_widget(self._label(info['title'],16,PINK,True,height=dp(48)))
        box.add_widget(self._label(f"UP主：{info['owner']}  ·  时长：{fmt_time(info['duration'])}\n播放 {fmt_num(info['view'])}  ·  弹幕 {fmt_num(info['danmaku'])}  ·  评论 {fmt_num(info['reply'])}",12,MUTED,height=dp(48)))
        box.add_widget(self._label('选择接口实际返回的可用画质',13,TEXT,True,height=dp(28)))
        selected={'option':options[0]}
        for opt in options[:8]:
            b=self._btn(f"{opt['label']}  ·  {human_size(opt.get('size',0))}",lambda o=opt:selected.update(option=o),PINK_LIGHT,PINK,dp(38),True); box.add_widget(b)
        row=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8))
        popup=Popup(title='视频解析成功',content=box,size_hint=(.92,.83),auto_dismiss=True)
        row.add_widget(self._btn('取消',lambda:popup.dismiss(),PINK_LIGHT,PINK))
        row.add_widget(self._btn('开始下载',lambda:(popup.dismiss(),self._start_task_download(taskid,selected['option'])),PINK,WHITE,dp(44),True))
        box.add_widget(row); popup.open()
    def _start_task_download(self,taskid,option):
        if self.busy: self._popup('请稍候','当前有任务正在下载。'); return
        t=self._find_task(taskid)
        if not t: return
        self.busy=True; t.update({'status':'下载中','percent':0,'quality':option['label']}); self.show_home()
        threading.Thread(target=self._download_worker,args=(taskid,option),daemon=True).start()
    def _download_worker(self,taskid,option):
        t=self._find_task(taskid); info=(t or {}).get('info') or self.current_info
        try:
            outdir=os.path.join(self.user_data_dir,'downloads'); os.makedirs(outdir,exist_ok=True)
            name=safe_filename(info['title']); path=os.path.join(outdir,f"{name}_{info['bvid']}_{safe_filename(option['label'])}.mp4")
            def progress(done,total):
                p=done*100.0/total if total else 0
                Clock.schedule_once(lambda dt,d=done,tot=total,pc=p:self._progress_task(taskid,d,tot,pc),0)
            saved=download_stream(option['url'],path,progress)
            record={'id':taskid,'title':info['title'],'path':saved,'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'quality':option['label'],'bvid':info['bvid'],'cover_path':(t or {}).get('cover_path',''),'status':'已完成','percent':100,'created':(t or {}).get('created','')}
            Clock.schedule_once(lambda dt,r=record:self._download_done(taskid,r),0)
        except Exception as e: Clock.schedule_once(lambda dt,msg=str(e):self._download_error(taskid,msg),0)
    def _progress_task(self,taskid,done,total,p):
        t=self._find_task(taskid)
        if t: t['percent']=p; t['bytes']=done; t['total']=total
        # Refresh occasionally without rebuilding for every tiny network chunk.
        if t:
            last=int(t.get('_last_refresh_percent',-5))
            if int(p)>=last+5 or p>=100:
                t['_last_refresh_percent']=int(p)
                if self.page_name=='home': self.show_home()
    def _download_done(self,taskid,record):
        self.busy=False; t=self._find_task(taskid)
        if t: t.update(record)
        self.history=[h for h in self.history if h.get('id')!=taskid]; self.history.insert(0,record); self._save_history(); self.show_home()
        self._popup('下载完成',f"{record['title']}\n\n画质：{record['quality']}\n文件已保存到应用私有目录。\n{record['path']}\n\n可在“我的 → 已下载文件”中导出。")
    def _download_error(self,taskid,msg):
        self.busy=False; t=self._find_task(taskid)
        if t: t.update({'status':'已失败','error':msg})
        self.show_home(); self._popup('下载失败',msg[:900])
    def show_mine(self):
        self.page_name='mine'; self._scroll(); self._nav()
        profile=Surface(orientation='horizontal',size_hint_y=None,height=dp(102),padding=dp(14),spacing=dp(12))
        avatar_path=os.path.join(os.path.dirname(__file__),'assets','avatar-reference.jpg')
        profile.add_widget(Image(source=avatar_path,fit_mode='contain',size_hint_x=None,width=dp(105)) if os.path.isfile(avatar_path) else Label(text='♙',font_name=FONT,font_size='56sp',color=PINK,size_hint_x=None,width=dp(105)))
        col=BoxLayout(orientation='vertical',spacing=dp(4))
        col.add_widget(self._label('未登录',18,PINK,True,height=dp(35)))
        col.add_widget(self._label('点击此处登录',14,MUTED,height=dp(28)))
        profile.add_widget(col); profile.bind(on_touch_down=lambda w,t:self._login_info() if w.collide_point(*t.pos) else None)
        self.content.add_widget(profile)
        menu=Surface(orientation='vertical',size_hint_y=None,padding=0,spacing=0)
        rows=[('代码仓库','›',lambda:self._open_url('https://github.com/')),('当前版本','2.3.5.foss',None),('开源组件许可','›',self.show_licenses),('问题反馈','›',self.feedback)]
        for i,(title,value,cb) in enumerate(rows):
            r=BoxLayout(size_hint_y=None,height=dp(57),padding=[dp(15),0,dp(15),0])
            r.add_widget(self._label(title,15,(0.43,.42,.44,1),False,height=dp(56)))
            r.add_widget(self._label(value,15,PINK if title=='当前版本' else MUTED,title=='当前版本','right',dp(56)))
            if cb: r.bind(on_touch_down=lambda w,t,fn=cb:fn() if w.collide_point(*t.pos) else None)
            menu.add_widget(r)
            if i<len(rows)-1:
                with menu.canvas.after: Color(*BORDER); Line(points=[menu.x,menu.y,menu.x+menu.width,menu.y],width=0.7)
        self.content.add_widget(menu)
        for title,cb,red in [('设置',self.settings,False),('给我们评分',self.rate_app,False),('已下载文件',self.show_downloaded,False),('清除数据',self.clear_data,True)]:
            r=Surface(orientation='horizontal',size_hint_y=None,height=dp(58),padding=[dp(15),0,dp(15),0])
            r.add_widget(self._label(title,15,RED if red else (0.43,.42,.44,1),False,height=dp(55)))
            r.add_widget(self._label('›',30,MUTED,False,'right',dp(55)))
            r.bind(on_touch_down=lambda w,t,fn=cb:fn() if w.collide_point(*t.pos) else None)
            self.content.add_widget(r)
    def _login_info(self): self._popup('账号登录','当前版本暂未实现官方账号登录。需要高画质时，可在后续版本安全接入用户主动提供的 Cookie；请勿分享给他人。')
    def settings(self):
        self._popup('设置','BiliPink 设置\n\n语言：简体中文\n主题：B 站粉色 / 白色\n下载目录：应用私有目录\n文件名：保留中文标题\n\n提示：当前仅提供真实接口返回的直连 MP4 画质；不支持的 DASH 音视频合并会明确提示。')
    def show_licenses(self): self._popup('开源组件许可','BiliPink 使用 Kivy（MIT License）构建界面。\n\nPython 标准库组件遵循各自许可。\n\n字体文件 Noto Sans CJK（SIL Open Font License），若随 APK 打包则在项目 assets 中附带许可文件。')
    def feedback(self): self._popup('问题反馈','反馈时请提供：\n1. 视频链接类型（可遮挡个人信息）\n2. 解析或下载失败的完整提示\n3. 手机 Android 版本\n\n请勿提交账号密码或完整 Cookie。')
    def rate_app(self): self._popup('感谢支持','当前项目尚未发布到应用商店，暂时无法跳转评分。感谢你帮助测试 BiliPink！')
    def show_downloaded(self):
        self.page_name='mine'; self._scroll(); self._nav()
        self.content.add_widget(self._label('已下载文件',20,PINK,True,height=dp(38)))
        self.content.add_widget(self._label('视频保存在应用私有目录。点击导出可复制到手机公共下载目录（系统权限允许时）。',12,MUTED,height=dp(48)))
        if not self.history: self.content.add_widget(self._label('暂时没有已下载文件。',14,MUTED,False,'center',dp(70)))
        for rec in self.history:
            card=Surface(orientation='vertical',size_hint_y=None,padding=dp(12),spacing=dp(6))
            card.add_widget(self._label(rec.get('title','视频'),14,PINK,True,height=dp(38)))
            card.add_widget(self._label(f"{rec.get('quality','')}  ·  {rec.get('time','')}\n{rec.get('path','')}",11,MUTED,height=dp(42)))
            row=BoxLayout(size_hint_y=None,height=dp(42),spacing=dp(8))
            row.add_widget(self._btn('导出到手机',lambda r=rec:self.export_record(r),PINK,WHITE,dp(40),True))
            row.add_widget(self._btn('删除记录',lambda r=rec:self.delete_record(r),PINK_LIGHT,PINK,dp(40)))
            card.add_widget(row); self.content.add_widget(card)
        self.content.add_widget(self._btn('返回我的',self.show_mine,PINK_LIGHT,PINK))
    def export_record(self,rec):
        src=rec.get('path','')
        if not src or not os.path.isfile(src): self._popup('文件不存在','原文件已被移动或删除。'); return
        try:
            # Android 10+ scoped storage: use MediaStore when available.
            if platform=='android':
                from jnius import autoclass
                PythonActivity=autoclass('org.kivy.android.PythonActivity'); activity=PythonActivity.mActivity
                BuildVersion=autoclass('android.os.Build$VERSION'); ContentValues=autoclass('android.content.ContentValues')
                MediaStore=autoclass('android.provider.MediaStore$Video$Media'); values=ContentValues()
                filename=os.path.basename(src); values.put('_display_name',filename); values.put('mime_type','video/mp4'); values.put('relative_path','Download/BiliPink')
                resolver=activity.getContentResolver(); uri=resolver.insert(MediaStore.EXTERNAL_CONTENT_URI,values)
                if uri is None: raise RuntimeError('系统未允许创建公共下载文件')
                stream=resolver.openOutputStream(uri); inp=open(src,'rb')
                try:
                    while True:
                        chunk=inp.read(1024*1024)
                        if not chunk: break
                        stream.write(chunk)
                finally: inp.close(); stream.close()
                self._popup('导出完成',f'已导出到手机：Download/BiliPink/{filename}')
            else:
                destdir=os.path.join(os.path.expanduser('~'),'Downloads','BiliPink'); os.makedirs(destdir,exist_ok=True); dest=os.path.join(destdir,os.path.basename(src)); shutil.copy2(src,dest); self._popup('导出完成',dest)
        except Exception as e: self._popup('导出失败',f'{e}\n\n原文件仍保存在：\n{src}')
    def delete_record(self,rec):
        self.history=[h for h in self.history if h.get('id')!=rec.get('id')]
        self.tasks=[t for t in self.tasks if t.get('id')!=rec.get('id')]; self._save_history(); self.show_downloaded()
    def clear_data(self):
        box=BoxLayout(orientation='vertical',padding=dp(16),spacing=dp(12)); box.add_widget(self._label('确定清除下载历史和缓存吗？\n已下载的视频文件也会被删除。此操作不可撤销。',14,TEXT,height=dp(70)))
        pop=Popup(title='清除数据',content=box,size_hint=(.86,.36))
        row=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8)); row.add_widget(self._btn('取消',pop.dismiss,PINK_LIGHT,PINK)); row.add_widget(self._btn('确认清除',lambda:(pop.dismiss(),self._clear_all()),RED,WHITE)); box.add_widget(row); pop.open()
    def _clear_all(self):
        for r in self.history:
            p=r.get('path','')
            try:
                if p and os.path.isfile(p): os.remove(p)
            except OSError: pass
        self.history=[]; self.tasks=[]; self._save_history(); self.show_mine(); self._popup('已清除','下载历史与可删除的应用内视频文件已清除。')
    def _open_url(self,url):
        try:
            import webbrowser; webbrowser.open(url)
        except Exception: self._popup('代码仓库',url)
    def _popup(self,title,message):
        box=BoxLayout(orientation='vertical',padding=dp(15),spacing=dp(10)); lab=self._label(message,13,TEXT,height=dp(160)); box.add_widget(lab)
        pop=Popup(title=title,content=box,size_hint=(.88,.52),auto_dismiss=True)
        box.add_widget(self._btn('知道了',pop.dismiss,PINK,WHITE,dp(42),True)); pop.open()
    def _history_path(self): return os.path.join(self.user_data_dir,'history.json')
    def _load_history(self):
        try:
            with open(self._history_path(),'r',encoding='utf-8') as f: self.history=json.load(f)
            if not isinstance(self.history,list): self.history=[]
            self.tasks=[dict(h) for h in self.history]
        except Exception: self.history=[]; self.tasks=[]
    def _save_history(self):
        try:
            os.makedirs(self.user_data_dir,exist_ok=True)
            with open(self._history_path(),'w',encoding='utf-8') as f: json.dump(self.history,f,ensure_ascii=False,indent=2)
        except Exception: pass
    def on_start(self): self._load_history()

if __name__=='__main__': BiliPinkApp().run()
