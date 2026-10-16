[app]

title = BiliPink
package.name = bilipink
package.domain = org.bilipink

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ttf,otf,json,xml,txt
source.include_patterns = fonts/*

version = 1.0.0

orientation = portrait
fullscreen = 0

# 先精简依赖，降低 Android 编译的复杂度
requirements = python3,kivy==2.3.0,pillow

# Android SDK / NDK
android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

# 网络权限：请求B站接口、下载视频和音频
android.permissions = INTERNET,ACCESS_NETWORK_STATE

android.accept_sdk_license = True
android.debuggable = False

# 避免引用当前不存在的 assets/bdl-android-aarch64
# 中文字体放在 fonts/ 目录中
# 例如：fonts/NotoSansSC-Regular.otf

[buildozer]

log_level = 2
warn_on_root = 1
