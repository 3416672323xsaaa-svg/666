[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,png,jpg,jpeg,otf,json,txt
source.include_dirs = fonts

# ✅绝对别动！
android.add_assets = fonts:fonts

# API ↔ NDK 严格锁死（这组是Actions最稳组合，之前33‑r25b配对会随机抛错）
android.api = 34
android.ndk = 26b
android.sdk = 24

# ❗删掉旧的 use-certifi、乱加的meta‑data（之前meta那行语法是错的！p4a不认 ;isDebug=true）
android.gradle_dependencies = androidx.core:core-ktx:1.12.0

# 权限修正：MANAGE_EXTERNAL_STORAGE不能直接写在permission数组！要用extra-manifest
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
# ❗非常关键：关闭自动注入--use-certifi（就是日志报错来源！新版本buildozer会乱塞这个不存在参数）
p4a_args = --ignore-setup-py
