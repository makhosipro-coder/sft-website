[app]
title = Samsung Firmware Tool
package.name = sft
package.domain = org.sprutting
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,html,css,js,txt,md
version = 2.5.0
requirements = python3,kivy,flask,requests,jinja2,werkzeug
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.arch = arm64-v8a
android.allow_backup = True
osx.python_version = 3
osx.kivy_version = 2.1.0
[buildozer]
log_level = 2
warn_on_root = 1
