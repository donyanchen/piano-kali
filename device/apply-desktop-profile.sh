#!/bin/bash
# Apply the exported sheng desktop profile to this piano install.
set -u
k() { kwriteconfig6 --file "$1" --group "$2" --key "$3" "$4"; }

# --- kconfig whitelist -------------------------------------------------------
k kdeglobals General ColorScheme BreezeLight
k kdeglobals General accentColorFromWallpaper false
k kdeglobals KDE LookAndFeelPackage org.kde.breeze.desktop
k kdeglobals Icons Theme Colloid-Light
k kcminputrc Mouse cursorTheme Breeze_Light
k kcminputrc Mouse cursorSize 24
k plasmarc Theme name default
k kwinrc Desktops Number 1
k kwinrc Desktops Rows 1
k kwinrc org.kde.kdecoration2 library org.kde.breeze
k kwinrc org.kde.kdecoration2 theme Breeze
k kscreenlockerrc Daemon Autolock true
k kscreenlockerrc Daemon LockGrace 0
k kscreenlockerrc Daemon Timeout 60
k kscreenlockerrc Greeter WallpaperPlugin org.kde.image

# Power policy: KDE's own power key stays disabled, we own it.
for g in 'AC][SuspendAndShutdown' 'Battery][SuspendAndShutdown' 'LowBattery][SuspendAndShutdown'; do
    k powerdevilrc "$g" PowerButtonAction 0
    k powerdevilrc "$g" PowerDownAction 0
done
k powerdevilrc 'AC][SuspendAndShutdown' AutoSuspendAction 0
k powerdevilrc 'AC][SuspendAndShutdown' AutoSuspendIdleTimeoutSec 3600
for g in 'Battery][SuspendAndShutdown' 'LowBattery][SuspendAndShutdown'; do
    k powerdevilrc "$g" AutoSuspendAction 1
    k powerdevilrc "$g" AutoSuspendIdleTimeoutSec 1800
done
for spec in 'AC][Display 3600' 'Battery][Display 1800' 'LowBattery][Display 1800'; do
    g=${spec% *}; t=${spec##* }
    k powerdevilrc "$g" TurnOffDisplayWhenIdle true
    k powerdevilrc "$g" TurnOffDisplayIdleTimeoutSec "$t"
    k powerdevilrc "$g" TurnOffDisplayIdleTimeoutWhenLockedSec 0
    k powerdevilrc "$g" LockBeforeTurnOffDisplay true
done
echo kconfig-done
