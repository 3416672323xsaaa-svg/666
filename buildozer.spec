[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf
source.include_dirs = fonts
version = 1.0

android.api = 33
android.ndk = r25b
android.build_tools = 33.0.2
android.archs = arm64-v8a
android.add_assets = fonts:fonts
android.copy_libs = 1

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO
android.meta_data = android.permission.MANAGE_EXTERNAL_STORAGE;android:name=android.permission.MANAGE_EXTERNAL_STORAGE

requirements = python3==3.11,kivy==2.3.1,kivymd==1.2.0,requests,yt-dlp==2026.3.22
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 0
android.accept_sdk_license = true
env = P4A_DOWNLOAD_HOST=https://mirrors.aliyun.com/android
