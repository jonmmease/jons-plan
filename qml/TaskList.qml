import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * Task list component showing tasks for the selected phase.
 * Displays task status icons and names.
 */
ColumnLayout {
    id: root
    spacing: Theme.spacingTiny

    Repeater {
        model: workflowModel.selectedPhaseTasks || []

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: taskRow.height + Theme.spacingSmall
            color: "transparent"

            RowLayout {
                id: taskRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSmall

                // Status icon
                Text {
                    text: {
                        switch(modelData.status) {
                            case "done": return "\u2713"       // Checkmark
                            case "in-progress": return "\u25CF" // Filled circle
                            case "blocked": return "\u2716"    // X mark
                            default: return "\u25CB"           // Empty circle
                        }
                    }
                    font.pixelSize: Theme.fontSizeNormal
                    color: {
                        switch(modelData.status) {
                            case "done": return Theme.statusCompleted
                            case "in-progress": return Theme.statusInProgress
                            case "blocked": return "#f44336"  // Red
                            default: return Theme.statusTodo
                        }
                    }
                    Layout.preferredWidth: 20
                    horizontalAlignment: Text.AlignHCenter
                }

                // Task description
                Text {
                    text: modelData.description || modelData.id
                    font.pixelSize: Theme.fontSizeSmall
                    color: modelData.status === "done" ? Theme.textSecondary : Theme.textPrimary
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // Hover background
            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: Theme.radiusSmall
                color: Theme.hoverHighlight
                opacity: 0.2
                visible: taskMouseArea.containsMouse
            }

            MouseArea {
                id: taskMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor

                ToolTip.visible: containsMouse && modelData.steps && modelData.steps.length > 0
                ToolTip.text: {
                    if (!modelData.steps) return ""
                    return "Steps:\n" + modelData.steps.map((s, i) => (i+1) + ". " + s).join("\n")
                }
                ToolTip.delay: 500
            }
        }
    }

    // Empty state
    Text {
        text: "No tasks"
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textMuted
        visible: (workflowModel.selectedPhaseTasks || []).length === 0
    }
}
