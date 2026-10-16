[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf,kv,json,xml
source.include_dirs = fonts
source.exclude_dirs = tests, __pycache__, venv

version = 0.3

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.build_tools = 33.0.2
android.archs = arm64-v8a

python3 = 3.11
hostpython3 = 3.11

# ⚠️注意：这里没有写 yt‑dlp / ffmpeg；两个二进制由APP运行时联网自动下载
requirements = python3==3.11,kivy==2.3.0,kivymd==1.2.0,requests,pillow

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,POST_NOTIFICATIONS

# MANAGE_EXTERNAL_STORAGE 需要这个特殊标记（Android11+）
android.uses-permission = android.permission.MANAGE_EXTERNAL_STORAGE
android.uses-permission = android.permission.POST_NOTIFICATIONS

android.accept_sdk_license = True
android.allow_backup = True
android.debuggable = True

[buildozer]
log_level = 2
warn_on_root = 0
