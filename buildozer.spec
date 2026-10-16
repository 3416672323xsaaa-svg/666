[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
# ✅就是这行之前漏掉！必须要有
version = 0.1

source.dir = .
source.include_exts = py,png,jpg,jpeg,otf,json,txt
source.include_dirs = fonts

# ✅钉死不动
android.add_assets = fonts:fonts

android.api = 33
android.ndk = 25b
android.sdk = 24
android.gradle_dependencies = androidx.core:core-ktx:1.12.0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO
android.extra_manifest_xml = ./manifest-append.xml

android.enable_androidx = True
android.use_aar = True

requirements = python3==3.11,kivy==2.3.0,urllib3,requests,yt-dlp==2026.9.25

android.p4a_bootstrap = sdl2
android.p4a_apk_format = debug

android.icon = fonts/icon.png
android.presplash_color = #F26A8D
android.copy_fonts = False

source.exclude_patterns = __pycache__,*.pyc,.git,*.md

[buildozer]
log_level = 2
warn_on_root = 0
p4a_args = --ignore-setup-py --no-certifi
