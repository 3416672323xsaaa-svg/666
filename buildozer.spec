[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf,kv,atlas,json,xml,java
source.include_patterns = assets/*,fonts/*,src/*

version = 2.5.1
orientation = portrait
fullscreen = 0

# 固定python3.11，certifi已加入，解决ssl _ssl.c:1006
requirements = python3==3.10,kivy==2.3.0,kivymd==1.1.1,pillow,pyjnius,certifi

android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

# =========关键：把fonts文件夹打入APK Assets！main.py从assets读取otf字体=========
android.add_assets = fonts

# 补齐存储网络权限，适配Android13
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE

android.add_src = src

android.debuggable = True

[buildozer]
log_level = 2
warn_on_root = 1
