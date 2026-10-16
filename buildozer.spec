[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,otf,json,xml,txt
source.include_patterns = fonts/*

version = 1.0.0

orientation = portrait
fullscreen = 0

requirements = python3,kivy==2.3.0,kivymd==1.1.1,pillow,requests,certifi

android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES

android.accept_sdk_license = True
android.debuggable = False

[buildozer]

log_level = 2
warn_on_root = 0
