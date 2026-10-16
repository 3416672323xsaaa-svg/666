[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
source.dir = .
source.include_exts = py,kv,json
# 资源完全交给 android.add_assets；这里只抓源码，不带任何资源
source.include_patterns =
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__
version = 1.1.0
orientation = portrait
fullscreen = 0

requirements = python3,kivy==2.3.0,kivymd==1.2.0,jnius,certifi,requests,plyer

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,POST_NOTIFICATIONS,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 30
android.ndk = 25c
android.ndk_api = 30
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True

# ⚠️文件级映射！只把 fonts/NotoSansSC‑Regular.otf → assets/fonts/NotoSansSC‑Regular.otf
# avatar-reference.jpg 完全没写，就不会进assets
android.add_assets = fonts/NotoSansSC-Regular.otf:assets/fonts/NotoSansSC-Regular.otf

p4a.extra_args = --use-certifi
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
