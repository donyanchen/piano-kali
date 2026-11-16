#!/bin/bash
# Screen-lock idle timeout is global in Plasma; follow the active power profile.
set -euo pipefail
minutes=${1:?Expected screen lock timeout in minutes}
[[ "$minutes" =~ ^[1-9][0-9]*$ ]] && (( minutes <= 1440 )) || exit 2
kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock true
kwriteconfig6 --file kscreenlockerrc --group Daemon --key Timeout "$minutes"
kwriteconfig6 --file kscreenlockerrc --group Daemon --key LockGrace 0
qdbus6 org.freedesktop.ScreenSaver /ScreenSaver org.kde.screensaver.configure
