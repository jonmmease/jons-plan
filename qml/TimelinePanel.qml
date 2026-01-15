import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * Timeline panel showing recent progress entries.
 */
Rectangle {
    id: root
    color: Theme.bgTimeline

    ListView {
        id: listView
        anchors.fill: parent
        anchors.margins: Theme.spacingSmall
        clip: true
        model: workflowModel.progressEntries
        spacing: Theme.spacingTiny

        // Auto-scroll to bottom when entries change
        onCountChanged: {
            if (count > 0) {
                positionViewAtEnd()
            }
        }

        delegate: Rectangle {
            width: listView.width
            height: entryRow.height + Theme.spacingSmall
            color: "transparent"

            RowLayout {
                id: entryRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSmall

                // Type indicator
                Rectangle {
                    width: 4
                    height: parent.height
                    radius: 2
                    color: {
                        switch(modelData.type) {
                            case "phase": return Theme.statusCurrent
                            case "task": return Theme.statusCompleted
                            case "session": return Theme.statusInProgress
                            default: return Theme.textMuted
                        }
                    }
                }

                // Timestamp
                Text {
                    text: modelData.timestamp.split(" ")[1] || modelData.timestamp
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: "Menlo"
                    color: Theme.textMuted
                    Layout.preferredWidth: 60
                }

                // Message
                Text {
                    text: modelData.message
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textPrimary
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        // Empty state
        Text {
            anchors.centerIn: parent
            text: "No progress entries"
            font.pixelSize: Theme.fontSizeNormal
            color: Theme.textMuted
            visible: listView.count === 0
        }
    }
}
