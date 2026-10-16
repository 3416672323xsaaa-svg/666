[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf
source.include_dirs = fonts
version = 1.0

android.api = 33
android.ndk = 25.2.9519653
android.build_tools = 33.0.2
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE
android.archs = arm64-v8a

requirements = python3==3.11,kivy==2.3.0,kivymd==1.2.0,requests,yt-dlp
orientation = portrait
fullscreen = 0

[p4a.env]
P4A_SDK = %(ANDROID_HOME)s
P4A_ANDROID_NDK = %(ANDROID_HOME)s/ndk/25.2.9519653

[buildozer]
log_level = 2
warn_on_root = 0
android.accept_sdk_license = True
