[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf,kv,json,xml
source.include_patterns = fonts/*

version = 1.0

orientation = portrait
fullscreen = 0

# Android SDK / NDK
android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools = 33.0.2
android.archs = arm64-v8a

# Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES

# Python dependencies
requirements = python3,kivy==2.3.1,kivymd==1.2.0,requests,yt-dlp==2026.3.22

# Android application settings
android.accept_sdk_license = True
android.allow_backup = True
android.debug = 0

[buildozer]
log_level = 2
warn_on_root = 0
