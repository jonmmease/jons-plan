import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * PhaseHistory - Linear listing of phase entries in chronological order.
 * Shows numbered entries (01-Research, 02-Plan, etc.) with selection support.
 */
Rectangle {
    id: root
    color: Theme.bgPanel

    // Header
    Rectangle {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 32
        color: Theme.bgPanelHeader

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingMedium
            anchors.rightMargin: Theme.spacingMedium

            Text {
                text: "Phase History"
                font.pixelSize: Theme.fontSizeNormal
                font.weight: Font.Medium
                color: Theme.textPrimary
            }

            Text {
                text: "(" + workflowModel.phaseHistory.length + " entries)"
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            Item { Layout.fillWidth: true }
        }
    }

    // Phase list
    ScrollView {
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        clip: true

        ListView {
            id: historyList
            model: workflowModel.phaseHistory
            spacing: 1

            delegate: Rectangle {
                width: historyList.width
                height: entryContent.height + Theme.spacingSmall * 2
                color: {
                    if (workflowModel.selectedPhaseEntry === modelData.entry) {
                        return Theme.taskSelectedBg
                    } else if (entryMouse.containsMouse) {
                        return Theme.hoverHighlight
                    }
                    return "transparent"
                }

                RowLayout {
                    id: entryContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: Theme.spacingMedium
                    anchors.rightMargin: Theme.spacingMedium
                    spacing: Theme.spacingSmall

                    // Entry number badge
                    Rectangle {
                        width: 28
                        height: 20
                        radius: Theme.radiusSmall
                        color: {
                            var status = getPhaseStatus(modelData.phase)
                            switch(status) {
                                case "current": return Theme.nodeCurrentBg
                                case "completed": return Theme.nodeCompletedBg
                                case "terminal": return Theme.nodeTerminalBg
                                default: return Theme.nodePendingBg
                            }
                        }
                        border.width: 1
                        border.color: {
                            var status = getPhaseStatus(modelData.phase)
                            switch(status) {
                                case "current": return Theme.nodeCurrentBorder
                                case "completed": return Theme.nodeCompletedBorder
                                case "terminal": return Theme.nodeTerminalBorder
                                default: return Theme.nodePendingBorder
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: String(modelData.entry).padStart(2, "0")
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }
                    }

                    // Phase name
                    Text {
                        Layout.fillWidth: true
                        text: formatPhaseName(modelData.phase)
                        font.pixelSize: Theme.fontSizeNormal
                        color: Theme.textPrimary
                        elide: Text.ElideRight
                    }

                    // Outcome indicator
                    Text {
                        visible: modelData.outcome !== undefined
                        text: modelData.outcome === "completed" ? "✓" : ""
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.nodeCompletedBorder
                        font.weight: Font.Bold
                    }
                }

                MouseArea {
                    id: entryMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: workflowModel.selectPhaseEntry(modelData.entry)
                }
            }
        }
    }

    // Helper functions
    function formatPhaseName(phaseId) {
        return phaseId.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase())
    }

    function getPhaseStatus(phaseId) {
        var nodes = workflowModel.nodes
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].id === phaseId) {
                return nodes[i].status
            }
        }
        return "pending"
    }
}
