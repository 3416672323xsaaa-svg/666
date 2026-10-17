[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,ttc,otf,kv,atlas,json,xml,java
source.include_patterns = fonts/*,src/*

version = 2.5.3
orientation = portrait
fullscreen = 0

# APK 桌面图标
icon.filename = %(source.dir)s/bilipink图标.png

# 原生启动加载图
presplash.filename = %(source.dir)s/bilipink加载图.png

requirements = python3,kivy==2.2.1,kivymd==1.1.1,pillow,pyjnius,certifi

p4a.python_version = 3.10

android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

# 打包字体资源
android.add_assets = fonts

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE

# 如果仓库中存在 src 文件夹并且需要打包 Java 源码，则保留
android.add_src = src

android.debuggable = True

[buildozer]

log_level = 2
warn_on_root = 1
