import QtQuick
import org.kde.kwin as KWin

Item {
    id: policy
    readonly property var focused: KWin.Workspace.activeWindow
    readonly property var watched: {
        var win = focused
        for (var i = 0; win && win.transientFor && i < 10; i++) win = win.transientFor
        return win
    }
    property int lastMode: -1
    function update() {
        var win = watched
        var hidden = !!(win && win.caption !== "Sheng Application Drawer" && !win.deleted && !win.minimized && !win.desktopWindow
            && (win.normalWindow || win.dialog) && (win.fullScreen || Number(win.maximizeMode) === 3))
        if (lastMode === Number(hidden)) return
        lastMode = Number(hidden)
        request.arguments = [hidden]
        request.call()
    }
    KWin.DBusCall {
        id: request
        service: "org.sheng.DesktopPolicy"
        path: "/org/sheng/DesktopPolicy"
        dbusInterface: "org.sheng.DesktopPolicy"
        method: "SetDockHidden"
    }
    onWatchedChanged: settle.restart()
    Connections {
        target: policy.watched
        ignoreUnknownSignals: true
        function onFullScreenChanged() { settle.restart() }
        function onMaximizedChanged() { settle.restart() }
        function onMinimizedChanged() { settle.restart() }
    }
    Timer { id: settle; interval: 100; onTriggered: policy.update() }
    Component.onCompleted: settle.start()
}
