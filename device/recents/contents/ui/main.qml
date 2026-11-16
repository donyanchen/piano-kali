import QtQuick
import org.kde.kwin as KWin

KWin.SceneEffect {
    id: recents
    property var history: []
    property var entries: []
    property bool expanded: false
    property int selectedIndex: 0
    property var pendingWindow: null
    DesktopPolicy { }

    function eligible(win) {
        return win && !win.deleted && (win.normalWindow || win.dialog)
            && !win.skipTaskbar && !win.skipSwitcher
            && (!win.activities.length || win.activities.indexOf(KWin.Workspace.currentActivity) >= 0)
    }
    function key(win) { return String(win.internalId) }
    function remember(win) {
        if (!eligible(win)) return
        var id = key(win)
        history = [id].concat(history.filter(k => k !== id))
    }
    function windows() {
        var all = KWin.Workspace.stackingOrder.filter(win => eligible(win)).reverse()
        all.sort((a, b) => {
            var ai = history.indexOf(key(a)), bi = history.indexOf(key(b))
            return (ai < 0 ? 100000 : ai) - (bi < 0 ? 100000 : bi)
        })
        return all
    }
    function refresh() {
        entries = windows()
        selectedIndex = Math.max(0, Math.min(selectedIndex, entries.length - 1))
        history = history.filter(id => entries.some(win => key(win) === id))
    }
    function showTasks() {
        closeTimer.stop()
        pendingWindow = null
        refresh()
        selectedIndex = 0
        expanded = true
        visible = true
        console.info("SHENG_RECENTS opened", entries.length)
    }
    function toggleTasks() {
        if (visible) dismiss(null)
        else showTasks()
    }
    function leaveImmediately() {
        closeTimer.stop()
        pendingWindow = null
        expanded = false
        visible = false
    }
    function dismiss(win) {
        pendingWindow = win
        expanded = false
        closeTimer.restart()
    }
    function moveSelection(delta) {
        if (entries.length) selectedIndex = (selectedIndex + delta + entries.length) % entries.length
    }
    function closeWindow(win) {
        if (!win || !win.closeable) return
        // Normal window close lets applications display their own save prompts.
        dismiss(null)
        win.closeWindow()
    }
    function closeAll() {
        var targets = entries.slice()
        dismiss(null)
        targets.forEach(win => { if (eligible(win) && win.closeable) win.closeWindow() })
    }

    Timer {
        id: closeTimer
        interval: 240
        onTriggered: {
            var target = recents.pendingWindow
            recents.pendingWindow = null
            recents.visible = false
            if (recents.eligible(target)) {
                target.minimized = false
                KWin.Workspace.activeWindow = target
                recents.remember(target)
            }
        }
    }
    Connections {
        target: KWin.Workspace
        function onWindowActivated(win) { recents.remember(win) }
        function onWindowAdded(win) {
            if (recents.visible) Qt.callLater(recents.refresh)
        }
        function onWindowRemoved(win) {
            var id = recents.key(win)
            recents.history = recents.history.filter(k => k !== id)
            if (recents.visible) Qt.callLater(recents.refresh)
        }
    }
    KWin.ShortcutHandler {
        name: "Sheng Task Cards"
        text: "显示平板后台任务卡片"
        sequence: "Meta+W"
        onActivated: recents.toggleTasks()
    }
    KWin.ShortcutHandler {
        name: "Sheng Leave Task Cards"
        text: "退出平板后台任务卡片"
        onActivated: recents.leaveImmediately()
    }
    // Reserve these gestures in KWin so applications do not receive stray
    // three-finger input. The native libinput bridge handles their full path.
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchpad; direction: KWin.SwipeGestureHandler.Up }
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchpad; direction: KWin.SwipeGestureHandler.Down }
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchpad; direction: KWin.SwipeGestureHandler.Left }
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchpad; direction: KWin.SwipeGestureHandler.Right }
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchscreen; direction: KWin.SwipeGestureHandler.Up }
    KWin.SwipeGestureHandler { fingerCount: 3; deviceType: KWin.SwipeGestureHandler.Touchscreen; direction: KWin.SwipeGestureHandler.Down }

    delegate: TasksView { controller: recents }
    Component.onCompleted: {
        remember(KWin.Workspace.activeWindow)
        console.info("SHENG_RECENTS ready horizontal-only-v2")
    }
}
