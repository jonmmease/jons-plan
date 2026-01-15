import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * PhaseHistoryList - List content for phase history entries.
 * Used inside AccordionSection; header is provided externally.
 */
Rectangle {
    id: root
    color: Theme.bgPanel
    focus: true

    // Track if last navigation was via keyboard (disables hover highlight)
    property bool keyboardNav: false

    // Keyboard navigation
    Keys.onUpPressed: {
        keyboardNav = true
        var current = workflowModel.selectedPhaseEntry
        if (current > 1) {
            workflowModel.selectPhaseEntry(current - 1)
        }
    }
    Keys.onDownPressed: {
        keyboardNav = true
        var current = workflowModel.selectedPhaseEntry
        if (current < workflowModel.phaseHistory.length) {
            workflowModel.selectPhaseEntry(current + 1)
        }
    }

    // Phase list
    ScrollView {
        anchors.fill: parent
        clip: true

        ListView {
            id: historyList
            model: workflowModel.phaseHistory
            spacing: 1

            // Scroll to selected entry when it changes
            Connections {
                target: workflowModel
                function onSelectedPhaseEntryChanged() {
                    var idx = workflowModel.selectedPhaseEntry - 1
                    if (idx >= 0 && idx < historyList.count) {
                        historyList.positionViewAtIndex(idx, ListView.Contain)
                    }
                }
            }

            delegate: Rectangle {
                width: historyList.width
                height: entryContent.height + Theme.spacingSmall * 2
                color: {
                    if (workflowModel.selectedPhaseEntry === modelData.entry) {
                        return Theme.taskSelectedBg
                    } else if (entryMouse.containsMouse && !root.keyboardNav) {
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
                    onPositionChanged: root.keyboardNav = false
                    onClicked: {
                        root.keyboardNav = false
                        root.forceActiveFocus()
                        workflowModel.selectPhaseEntry(modelData.entry)
                    }
                }
            }

            // Empty state
            Text {
                anchors.centerIn: parent
                text: "No phase entries"
                font.pixelSize: Theme.fontSizeNormal
                color: Theme.textMuted
                visible: historyList.count === 0
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
