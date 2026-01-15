import QtQuick
import QtQuick.Layouts
import "theme"

/**
 * TreeNode - Recursive component for rendering task tree nodes.
 * Displays a task with status icon, description, and nested children.
 */
Item {
    id: root

    property var task: null         // Task object {id, description, status, steps, parents}
    property int depth: 0           // Nesting depth (0 = root)
    property bool isRepeat: false   // True if this task appears elsewhere in tree
    property var children: []       // Array of child node objects
    property string selectedTaskId: ""  // ID of selected task (for highlighting)

    property bool isSelected: root.task && root.selectedTaskId === root.task.id
    property bool isHovered: mouseArea.containsMouse

    signal taskClicked(var task)

    implicitWidth: parent ? parent.width : 200
    implicitHeight: nodeContent.height + childrenColumn.height

    // Node content row
    Rectangle {
        id: nodeContent
        width: parent.width
        height: Theme.taskNodeHeight
        color: root.isSelected ? Theme.taskSelectedBg :
               root.isHovered ? Theme.hoverHighlight : "transparent"
        radius: Theme.radiusSmall

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: root.depth * Theme.treeIndent + Theme.spacingSmall
            anchors.rightMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            // Status icon - green checkmark for done
            Text {
                id: statusIcon
                Layout.preferredWidth: 20
                font.pixelSize: 16
                horizontalAlignment: Text.AlignHCenter
                text: {
                    var status = root.task ? root.task.status : ""
                    switch(status) {
                        case "done": return "✓"
                        case "in-progress": return "●"
                        case "blocked": return "✕"
                        default: return "○"
                    }
                }
                color: {
                    var status = root.task ? root.task.status : ""
                    switch(status) {
                        case "done": return "#4caf50"  // Green
                        case "in-progress": return "#ff9800"  // Orange
                        case "blocked": return "#f44336"  // Red
                        default: return "#9e9e9e"  // Gray
                    }
                }
                font.weight: Font.Bold
            }

            // Task description
            Text {
                Layout.fillWidth: true
                text: root.task ? (root.task.description || root.task.id || "") : ""
                font.pixelSize: Theme.fontSizeNormal
                color: Theme.textPrimary
                elide: Text.ElideRight
            }

            // Repeat marker
            Text {
                visible: root.isRepeat
                text: "↗"
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textMuted
                Layout.rightMargin: Theme.spacingTiny
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.taskClicked(root.task)
        }
    }

    // Children column (only for non-repeat nodes)
    Column {
        id: childrenColumn
        anchors.top: nodeContent.bottom
        width: parent.width
        visible: !root.isRepeat && root.children && root.children.length > 0

        Repeater {
            model: root.isRepeat ? [] : (root.children || [])

            // Use Loader with source URL to break recursive instantiation
            Loader {
                id: childLoader
                width: childrenColumn.width
                height: item ? item.implicitHeight : 0

                property var childData: modelData

                source: "TreeNode.qml"
                onLoaded: {
                    item.task = childData.task
                    item.depth = root.depth + 1
                    item.isRepeat = childData.isRepeat
                    item.children = childData.children
                    item.selectedTaskId = Qt.binding(function() { return root.selectedTaskId })
                    item.taskClicked.connect(function(clickedTask) {
                        root.taskClicked(clickedTask)
                    })
                }
            }
        }
    }
}
