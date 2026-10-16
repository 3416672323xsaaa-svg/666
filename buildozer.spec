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

# 先使用精简依赖，降低原生扩展编译的复杂度
requirements = python3,kivy==2.3.0,pillow

# Android 构建参数
android.api = 33
android.minapi = 24
android.ndk = 25c
android.archs = arm64-v8a

# 网络权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE

android.accept_sdk_license = True
android.debuggable = False

# 不配置不存在的 assets 目录
# 中文字体放在 fonts/ 目录下

[buildozer]

log_level = 2
warn_on_root = 1
