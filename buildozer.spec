[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ttf,otf,json,xml,txt
source.include_patterns = fonts/*

version = 1.0.0

orientation = portrait
fullscreen = 0

requirements = python3,kivy==2.3.0,pillow

android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

android.permissions = INTERNET,ACCESS_NETWORK_STATE

android.accept_sdk_license = True
android.debuggable = False

# 固定旧版 Android Python 构建工具，避免默认选用 Python 3.14
p4a.branch = v2024.01.21

[buildozer]

log_level = 2
warn_on_root = 1
