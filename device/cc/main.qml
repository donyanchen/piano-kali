import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    property var st: ({ wifi: "enabled", ssid: "", bt: "no", bright: 50, vol: 40, playing: false })
    property bool dark: false
    property bool eye: false
    property bool dnd: false

    function run(cmd) { exec.connectSource(cmd) }
    function refresh() { exec.connectSource("piano-cc state") }

    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function (source, data) {
            var out = data["stdout"] || ""
            if (out.indexOf("wifi=") >= 0) {
                var o = {}
                out.split("\n").forEach(function (line) {
                    var i = line.indexOf("=")
                    if (i > 0) o[line.slice(0, i)] = line.slice(i + 1).trim()
                })
                root.st = { wifi: o.wifi || "", ssid: o.ssid || "", bt: o.bt || "",
                            bright: parseInt(o.bright || "50"), vol: parseInt(o.vol || "40"),
                            playing: false }
            }
            disconnectSource(source)
        }
    }

    Timer { interval: 4000; running: root.expanded; repeat: true; onTriggered: root.refresh() }
    Component.onCompleted: root.refresh()

    compactRepresentation: MouseArea {
        Layout.minimumWidth: Kirigami.Units.iconSizes.smallMedium
        Layout.minimumHeight: Kirigami.Units.iconSizes.smallMedium
        onClicked: root.expanded = !root.expanded
        Kirigami.Icon {
            anchors.centerIn: parent
            source: "preferences-system"
            width: Kirigami.Units.iconSizes.smallMedium
            height: width
        }
    }

    fullRepresentation: Rectangle {
        id: panel
        Layout.preferredWidth: 520
        Layout.preferredHeight: 680
        radius: 30
        color: root.dark ? "#17191f" : "#f2f4f8"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            // header
            RowLayout {
                Layout.fillWidth: true
                Column {
                    Text {
                        text: Qt.formatDateTime(new Date(), "HH:mm")
                        color: root.dark ? "#ffffff" : "#111318"
                        font.pixelSize: 44; font.bold: true
                    }
                    Text {
                        text: Qt.formatDateTime(new Date(), "M月d日 dddd")
                        color: root.dark ? "#9aa4b2" : "#6b7280"; font.pixelSize: 13
                    }
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "99%"
                    color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 15
                }
                Kirigami.Icon {
                    source: "preferences-system"
                    width: 26; height: 26
                    color: root.dark ? "#ffffff" : "#111318"
                    MouseArea { anchors.fill: parent; onClicked: root.run("systemsettings") }
                }
            }

            // wifi + bluetooth cards
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 96; radius: 24
                    color: root.st.wifi === "enabled" ? "#2f6bff" : (root.dark ? "#23262e" : "#e6e9ef")
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 16; spacing: 12
                        Kirigami.Icon {
                            source: "network-wireless"
                            width: 30; height: 30
                            color: root.st.wifi === "enabled" ? "#ffffff" : (root.dark ? "#cfd6e4" : "#3a3f4b")
                        }
                        Column {
                            Layout.fillWidth: true; spacing: 2
                            Text {
                                text: root.st.ssid || "Wi-Fi"
                                color: root.st.wifi === "enabled" ? "#ffffff" : (root.dark ? "#ffffff" : "#111318")
                                font.pixelSize: 17; font.bold: true
                                elide: Text.ElideRight
                                width: parent.width
                            }
                            Text {
                                text: root.st.wifi === "enabled" ? "已连接" : "已关闭"
                                color: root.st.wifi === "enabled" ? "#dbe4ff" : "#7a8291"
                                font.pixelSize: 12
                            }
                        }
                        Text {
                            text: "›"; font.pixelSize: 26
                            color: root.st.wifi === "enabled" ? "#ffffff" : "#7a8291"
                        }
                    }
                    MouseArea { anchors.fill: parent; onClicked: { root.run("piano-cc wifi toggle"); root.refresh() } }
                }

                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 96; radius: 24
                    color: root.st.bt === "yes" ? "#2f6bff" : (root.dark ? "#23262e" : "#e6e9ef")
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 16; spacing: 12
                        Kirigami.Icon {
                            source: "bluetooth"
                            width: 30; height: 30
                            color: root.st.bt === "yes" ? "#ffffff" : (root.dark ? "#cfd6e4" : "#3a3f4b")
                        }
                        Column {
                            Layout.fillWidth: true; spacing: 2
                            Text {
                                text: "蓝牙"
                                color: root.st.bt === "yes" ? "#ffffff" : (root.dark ? "#ffffff" : "#111318")
                                font.pixelSize: 17; font.bold: true
                            }
                            Text {
                                text: root.st.bt === "yes" ? "已开启" : "已关闭"
                                color: root.st.bt === "yes" ? "#dbe4ff" : "#7a8291"
                                font.pixelSize: 12
                            }
                        }
                        Text { text: "›"; font.pixelSize: 26; color: root.st.bt === "yes" ? "#ffffff" : "#7a8291" }
                    }
                    MouseArea { anchors.fill: parent; onClicked: { root.run("piano-cc bt"); root.refresh() } }
                }
            }

            // music card + vertical sliders
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 250
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: 24
                    color: root.dark ? "#23262e" : "#e6e9ef"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 16
                        Kirigami.Icon { source: "audio-x-generic"; width: 26; height: 26
                                        color: root.dark ? "#cfd6e4" : "#3a3f4b" }
                        Text { text: "未在播放"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 16 }
                        Text { text: "音乐与媒体"; color: "#7a8291"; font.pixelSize: 12 }
                        Item { Layout.fillHeight: true }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 26
                            Text { text: "⏮"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 22 }
                            Text { text: "▶"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 26 }
                            Text { text: "⏭"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 22 }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 96; Layout.fillHeight: true; radius: 24
                    color: root.dark ? "#23262e" : "#e6e9ef"
                    Text { anchors.top: parent.top; anchors.topMargin: 12; anchors.horizontalCenter: parent.horizontalCenter
                           text: Math.round(brightV.value) + "%"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 13 }
                    Rectangle {
                        id: brightTrack
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top; anchors.topMargin: 44
                        width: 26; height: parent.height - 120; radius: 13
                        color: root.dark ? "#31353f" : "#cfd4dd"
                        Rectangle {
                            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width; radius: 13
                            height: parent.height * (brightV.value / 100)
                            color: "#2f6bff"
                        }
                        MouseArea {
                            anchors.fill: parent
                            function setFromY(y) {
                                var f = 1 - Math.max(0, Math.min(parent.height, y)) / parent.height
                                brightV.value = Math.round(Math.max(5, f * 100))
                                root.run("piano-cc bright " + brightV.value)
                            }
                            onPressed: function(m) { setFromY(m.y) }
                            onPositionChanged: function(m) { if (pressed) setFromY(m.y) }
                        }
                    }
                    Column {
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 10; anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 2
                        Text { text: "☀"; color: "#2f6bff"; font.pixelSize: 18; anchors.horizontalCenter: parent.horizontalCenter }
                        Text { text: "亮度"; color: "#7a8291"; font.pixelSize: 11; anchors.horizontalCenter: parent.horizontalCenter }
                    }
                    property alias value: brightV.value
                }

                Rectangle {
                    Layout.preferredWidth: 96; Layout.fillHeight: true; radius: 24
                    color: root.dark ? "#23262e" : "#e6e9ef"
                    Text { anchors.top: parent.top; anchors.topMargin: 12; anchors.horizontalCenter: parent.horizontalCenter
                           text: Math.round(volV.value) + "%"; color: root.dark ? "#ffffff" : "#111318"; font.pixelSize: 13 }
                    Rectangle {
                        id: volTrack
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top; anchors.topMargin: 44
                        width: 26; height: parent.height - 120; radius: 13
                        color: root.dark ? "#31353f" : "#cfd4dd"
                        Rectangle {
                            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width; radius: 13
                            height: parent.height * (volV.value / 100)
                            color: "#2f6bff"
                        }
                        MouseArea {
                            anchors.fill: parent
                            function setFromY(y) {
                                var f = 1 - Math.max(0, Math.min(parent.height, y)) / parent.height
                                volV.value = Math.round(f * 100)
                                root.run("piano-cc vol " + volV.value)
                            }
                            onPressed: function(m) { setFromY(m.y) }
                            onPositionChanged: function(m) { if (pressed) setFromY(m.y) }
                        }
                    }
                    Column {
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 10; anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 2
                        Text { text: "🔊"; color: "#2f6bff"; font.pixelSize: 18; anchors.horizontalCenter: parent.horizontalCenter }
                        Text { text: "音量"; color: "#7a8291"; font.pixelSize: 11; anchors.horizontalCenter: parent.horizontalCenter }
                    }
                }
            }

            // circular buttons
            GridLayout {
                Layout.fillWidth: true
                columns: 4; columnSpacing: 10; rowSpacing: 10
                Repeater {
                    model: [
                        { label: "热点", action: "hotspot" },
                        { label: "飞行模式", action: "airplane" },
                        { label: "勿扰模式", action: "dnd" },
                        { label: "深色模式", action: "dark" },
                        { label: "护眼模式", action: "eye" },
                        { label: "隐私", action: "privacy" },
                        { label: "截屏", action: "shot" },
                        { label: "锁屏", action: "lock" }
                    ]
                    Column {
                        Layout.fillWidth: true
                        spacing: 6
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 62; height: 62; radius: 31
                            color: {
                                if (modelData.action === "dark" && root.dark) return "#2f6bff"
                                if (modelData.action === "eye" && root.eye) return "#2f6bff"
                                if (modelData.action === "dnd" && root.dnd) return "#2f6bff"
                                return root.dark ? "#23262e" : "#e6e9ef"
                            }
                            Text {
                                anchors.centerIn: parent
                                text: ({hotspot:"📶", airplane:"✈", dnd:"🔕", dark:"☾", eye:"💡", privacy:"🛡", shot:"⛶", lock:"🔒"})[modelData.action]
                                font.pixelSize: 24
                                color: root.dark ? "#ffffff" : "#111318"
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    switch (modelData.action) {
                                    case "dark": root.dark = !root.dark; break
                                    case "eye": root.eye = !root.eye;
                                        root.run("piano-cc eye " + (root.eye ? "on" : "off")); break
                                    case "dnd": root.dnd = !root.dnd; break
                                    case "shot": root.run("piano-cc shot"); break
                                    case "lock": root.run("piano-cc lock"); break
                                    case "airplane": root.run("piano-cc air"); root.refresh(); break
                                    case "hotspot": root.run("piano-cc hotspot"); break
                                    case "privacy": root.run("systemsettings kcm_privacy"); break
                                    }
                                }
                            }
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label
                            color: root.dark ? "#cfd6e4" : "#3a3f4b"
                            font.pixelSize: 11
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }

        // hidden value holders
        QtObject { id: brightV; property real value: root.st.bright }
        QtObject { id: volV; property real value: root.st.vol }
    }
}
