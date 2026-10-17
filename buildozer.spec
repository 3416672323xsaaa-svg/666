[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,ttc,otf,kv,atlas,json,xml,java
source.include_patterns = fonts/,src/

APK 桌面图标：使用仓库根目录中的 PNG 图片

icon.filename = %(source.dir)s/bilipink图标.png

version = 2.5.2
orientation = portrait
fullscreen = 0

requirements = python3,kivy==2.2.1,kivymd==1.1.1,pillow,pyjnius,certifi

p4a.python_version = 3.10

android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

将仓库中现有的 fonts 文件夹打包进 APK

android.add_assets = fonts

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE

只有仓库确实存在 src 文件夹并且需要打包 Java 源码时才保留

android.add_src = src

android.debuggable = True

[buildozer]

log_level = 2
warn_on_root = 1
