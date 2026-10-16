[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
version = 0.3

source.dir = .
source.include_exts = py,png,jpg,ttf,kv,json
source.include_dirs = fonts

android.uses-permission = INTERNET;WRITE_EXTERNAL_STORAGE;READ_EXTERNAL_STORAGE;ACCESS_NETWORK_STATE;MANAGE_EXTERNAL_STORAGE
# android.sdk = 24   ;已废弃，注释即可，不想动直接恢复原样
android.ndk = 28c
android.accept_sdk_license = True
android.env = LC_ALL=C.UTF-8;LANG=C.UTF-8;PYTHONIOENCODING=utf-8

requirements = python3==3.11,kivy,kivymd,requests

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
