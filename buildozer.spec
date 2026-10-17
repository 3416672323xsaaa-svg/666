[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,ttc,otf,kv,atlas,json,xml,java
source.include_patterns = fonts/*,src/*,assets/*

version = 2.5.2
orientation = portrait
fullscreen = 0

# 应用图标：放在项目根目录
icon.filename = %(source.dir)s/bilipink图标.png

# APK 启动时的加载图：放在项目根目录
presplash.filename = %(source.dir)s/bilipink加载图.png

# Python 与 UI 依赖
requirements = python3,kivy==2.2.1,kivymd==1.1.1,pillow,pyjnius,certifi
p4a.python_version = 3.10

# Android 构建设置
android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

# 附加资源和 Java 源码
android.add_assets = fonts
android.add_src = src

# 网络与媒体权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE

android.debuggable = True

[buildozer]
log_level = 2
warn_on_root = 1
