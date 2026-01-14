import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * Details panel showing information about the selected phase.
 */
Rectangle {
    id: root
    color: Theme.bgPanel

    // Empty state when no phase selected
    Text {
        anchors.centerIn: parent
        text: "Select a phase to view details"
        font.pixelSize: Theme.fontSizeNormal
        color: Theme.textMuted
        visible: workflowModel.selectedPhase === ""
    }

    // Phase details content
    ScrollView {
        anchors.fill: parent
        visible: workflowModel.selectedPhase !== ""
        clip: true

        ColumnLayout {
            width: root.width
            spacing: 0

            // Header
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: headerContent.height + Theme.spacingMedium * 2
                color: Theme.bgPanelHeader

                ColumnLayout {
                    id: headerContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingTiny

                    Text {
                        text: workflowModel.selectedPhaseDetails.name || ""
                        font.pixelSize: Theme.fontSizeHeader
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    RowLayout {
                        spacing: Theme.spacingMedium

                        // Status badge
                        Rectangle {
                            width: statusText.width + Theme.spacingSmall * 2
                            height: statusText.height + Theme.spacingTiny * 2
                            radius: Theme.radiusSmall
                            color: {
                                const node = workflowModel.nodes.find(n => n.id === workflowModel.selectedPhase)
                                if (!node) return Theme.nodePendingBg
                                switch(node.status) {
                                    case "current": return Theme.nodeCurrentBg
                                    case "completed": return Theme.nodeCompletedBg
                                    case "terminal": return Theme.nodeTerminalBg
                                    default: return Theme.nodePendingBg
                                }
                            }

                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                text: {
                                    const node = workflowModel.nodes.find(n => n.id === workflowModel.selectedPhase)
                                    if (!node) return "pending"
                                    return node.status
                                }
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textPrimary
                            }
                        }

                        // Entry count
                        Text {
                            text: (workflowModel.selectedPhaseDetails.entry_count || 0) + " entries"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                        }
                    }
                }
            }

            // Suggested next phases
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: nextContent.height + Theme.spacingMedium * 2
                color: Theme.bgPanel
                visible: (workflowModel.selectedPhaseDetails.suggested_next || []).length > 0

                ColumnLayout {
                    id: nextContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall

                    Text {
                        text: "Suggested Next"
                        font.pixelSize: Theme.fontSizeNormal
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSmall

                        Repeater {
                            model: workflowModel.selectedPhaseDetails.suggested_next || []

                            Rectangle {
                                width: nextLabel.width + Theme.spacingSmall * 2
                                height: nextLabel.height + Theme.spacingTiny * 2
                                radius: Theme.radiusSmall
                                color: Theme.bgPanelHeader

                                Text {
                                    id: nextLabel
                                    anchors.centerIn: parent
                                    text: modelData
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: Theme.textLink
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: workflowModel.selectPhase(modelData)
                                }
                            }
                        }
                    }
                }
            }

            // Separator
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Theme.bgPanelHeader
            }

            // Tasks section
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: tasksContent.height + Theme.spacingMedium * 2
                color: Theme.bgPanel
                visible: (workflowModel.selectedPhaseDetails.tasks || []).length > 0

                ColumnLayout {
                    id: tasksContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall

                    RowLayout {
                        Text {
                            text: "Tasks"
                            font.pixelSize: Theme.fontSizeNormal
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            property var tasks: workflowModel.selectedPhaseDetails.tasks || []
                            property int doneCount: tasks.filter(t => t.status === "done").length
                            text: doneCount + "/" + tasks.length + " done"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                        }
                    }

                    TaskList {
                        Layout.fillWidth: true
                    }
                }
            }

            // Phase prompt (collapsible)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: promptContent.height + Theme.spacingMedium * 2
                color: Theme.bgPanel

                property bool expanded: false

                ColumnLayout {
                    id: promptContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Phase Prompt"
                            font.pixelSize: Theme.fontSizeNormal
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: parent.parent.parent.expanded ? "Hide" : "Show"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textLink

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: promptContent.parent.expanded = !promptContent.parent.expanded
                            }
                        }
                    }

                    // Prompt text (shown when expanded)
                    Text {
                        Layout.fillWidth: true
                        text: workflowModel.selectedPhaseDetails.prompt || ""
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: "Menlo"
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        visible: promptContent.parent.expanded
                    }
                }
            }
        }
    }
}
