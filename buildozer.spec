[app]

title = SME小市值策略
package.name = sme_strategy
package.domain = org.qclaw

source.include_exts = py,png,jpg,kv,atlas,json

version = 0.1

requirements = python3,kivy==2.3.0,requests

orientation = portrait

osx.python_version = 3
osx.kivy_version = 2.3.0

fullscreen = 0

android.permissions = INTERNET

android.allow_backup = True

android.meta_data = com.google.android.gms.version=@integer/google_play_services_version

# Kivy 2.3.0
p4a.bootstrap = sdl2
p4a.kivy_version = 2.3.0

[buildozer]

log_level = 2

warn_on_root = 1

build_dir = ./build

bin_dir = ./bin
