[app]
title = BiliPink
package.name = bilipink
package.domain = org.bilipink
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,ttf,otf,xml,txt
source.include_patterns = assets/*
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__
version = 1.1.0
requirements = python3,kivy==2.3.0,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
# Compile/target SDK 33 is compatible with sideloaded apps on Android 11–14.
# minapi=30 restricts installation to Android 11 (API 30) and newer.
android.api = 33
android.minapi = 30
android.ndk = 25c
android.ndk_api = 30
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
