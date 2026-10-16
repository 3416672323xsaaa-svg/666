[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,ttf,kv,json
source.include_dirs = fonts

# 只写一次全部权限！不要复制多遍！
android.uses-permission = INTERNET;WRITE_EXTERNAL_STORAGE;READ_EXTERNAL_STORAGE;ACCESS_NETWORK_STATE;MANAGE_EXTERNAL_STORAGE

android.api = 33
android.ndk = 25b
android.sdk = 24
android.accept_sdk_license = True
android.env = LC_ALL=zh_CN.UTF-8;LANG=zh_CN.UTF-8;PYTHONIOENCODING=utf-8

requirements = python3==3.11,kivy,kivymd,requests

android.permissions = INTERNET

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
