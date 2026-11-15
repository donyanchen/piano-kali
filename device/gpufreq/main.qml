import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    property string mhz: "--"

    P5Support.DataSource {
        id: ex
        engine: "executable"
        connectedSources: []
        onNewData: function (source, data) {
            var out = (data["stdout"] || "").trim()
            if (out.length > 0) {
                var hz = parseInt(out)
                if (!isNaN(hz)) root.mhz = Math.round(hz / 1e6).toString()
            }
            disconnectSource(source)
        }
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: ex.connectSource("cat /sys/class/devfreq/3d00000.gpu/cur_freq")
    }

    compactRepresentation: RowLayout {
        spacing: 4
        Kirigami.Icon {
            source: "video-display"
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Kirigami.Units.iconSizes.small
        }
        Text {
            text: "GPU " + root.mhz + " MHz"
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            color: Kirigami.Theme.textColor
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: 160
        Layout.preferredHeight: 60
        Text {
            text: "GPU: " + root.mhz + " MHz"
            color: Kirigami.Theme.textColor
        }
        Text {
            text: "Adreno 830 / devfreq"
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
