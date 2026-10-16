[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf,kv,json,xml
source.include_dirs = fonts,assets

version = 0.1

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools = 33.0.2
android.archs = arm64-v8a

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES
android.meta_data = android.permission.MANAGE_EXTERNAL_STORAGE;android:name=android.permission.MANAGE_EXTERNAL_STORAGE

requirements = python3==3.11,kivy==2.3.1,kivymd==1.2.0,requests,yt-dlp==2025.12.29

android.accept_sdk_license = True
android.allow_backup = True
android.debuggable = True

[buildozer]
log_level = 2
warn_on_root = 0
