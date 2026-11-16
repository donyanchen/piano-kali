#!/bin/bash
set -euo pipefail
for profile in AC Battery LowBattery; do
    # Short press locks the session on every power source.
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key PowerButtonAction 32
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key PowerDownAction 8
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key SleepMode 1
    if [[ $profile == AC ]]; then idle_minutes=60; suspend_action=0; else idle_minutes=30; suspend_action=1; fi
    idle_seconds=$((idle_minutes * 60))
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key AutoSuspendAction "$suspend_action"
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key AutoSuspendIdleTimeoutSec "$idle_seconds"
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key TurnOffDisplayWhenIdle true
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key TurnOffDisplayIdleTimeoutSec "$idle_seconds"
    # Entering the lock screen blanks immediately; user activity still wakes it.
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key TurnOffDisplayIdleTimeoutWhenLockedSec 0
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key LockBeforeTurnOffDisplay true
    kwriteconfig6 --file powerdevilrc --group "$profile" --group RunScript --key ProfileLoadCommand "/usr/libexec/sheng-set-screen-lock-timeout $idle_minutes"
done
kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock true
kwriteconfig6 --file kscreenlockerrc --group Daemon --key Timeout 60
kwriteconfig6 --file kscreenlockerrc --group Daemon --key LockGrace 0
if [[ ${1:-} != --config-only ]]; then
    systemctl --user restart plasma-powerdevil.service
    profile=$(qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement org.kde.Solid.PowerManagement.currentProfile)
    if [[ $profile == AC ]]; then idle_minutes=60; else idle_minutes=30; fi
    /usr/libexec/sheng-set-screen-lock-timeout "$idle_minutes"
fi
