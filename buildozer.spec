[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink
version = 0.3
# ↑就是刚才缺的这一行！必须有

source.dir = .
source.include_exts = py,png,jpg,ttf,kv,json
source.include_dirs = fonts

# 权限只出现一次！绝对不要复制多遍
android.uses-permission = INTERNET;WRITE_EXTERNAL_STORAGE;READ_EXTERNAL_STORAGE;ACCESS_NETWORK_STATE;MANAGE_EXTERNAL_STORAGE

android.api = 33
android.ndk = 25b
android.sdk = 24
android.accept_sdk_license = True
android.env = LC_ALL=C.UTF-8;LANG=C.UTF-8;PYTHONIOENCODING=utf-8

requirements = python3==3.11,kivy,kivymd,requests

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
