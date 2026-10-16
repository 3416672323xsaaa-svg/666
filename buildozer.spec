[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,ttf,otf,xml,txt
source.include_patterns = assets/*,fonts/*
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__
version = 1.1.0
orientation = portrait
fullscreen = 0

# 全套依赖：certifi负责SSL；kivymd UI；yt-dlp下载；plyer通知
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pyjnius,certifi,requests,yt-dlp,plyer

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,POST_NOTIFICATIONS

android.api = 33
android.minapi = 30
android.ndk = 25c
android.ndk_api = 30
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True

# 最关键两行：①把fonts整个文件夹打入APK assets；②告诉p4a加载certifi证书包
android.add_assets = fonts:assets/fonts
android.extra_args = --use-certifi

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
