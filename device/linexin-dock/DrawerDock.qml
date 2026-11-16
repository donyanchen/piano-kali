        // KWin keeps the real panel above the fullscreen drawer. This nonvisual
        // compatibility endpoint keeps upstream keyboard fallback code valid.
        Item {
            id: runningDockContainer
            visible: false
            property QtObject taskRepeater: QtObject {
                readonly property int count: 0
                function itemAt(index) { return null }
            }
        }
