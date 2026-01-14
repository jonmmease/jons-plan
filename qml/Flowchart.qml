import QtQuick
import QtQuick.Shapes
import "theme"

/**
 * Flowchart visualization of workflow phases.
 * Renders nodes and edges using Graphviz-computed positions.
 */
Item {
    id: root

    // Coordinate transformation
    // Graphviz positions are in points, we scale to fit the view
    property real scale: 1.0
    property real offsetX: 50
    property real offsetY: 50

    // Compute bounds and scale on model change
    Component.onCompleted: computeTransform()
    Connections {
        target: workflowModel
        function onDataChanged() { computeTransform() }
    }

    function computeTransform() {
        if (workflowModel.nodes.length === 0) return

        // Find bounds
        let minX = Infinity, minY = Infinity
        let maxX = -Infinity, maxY = -Infinity

        for (let node of workflowModel.nodes) {
            minX = Math.min(minX, node.x - node.width/2)
            minY = Math.min(minY, node.y - node.height/2)
            maxX = Math.max(maxX, node.x + node.width/2)
            maxY = Math.max(maxY, node.y + node.height/2)
        }

        // Add padding
        const padding = 60
        const graphWidth = maxX - minX + padding * 2
        const graphHeight = maxY - minY + padding * 2

        // Calculate scale to fit
        const scaleX = (root.width - padding * 2) / graphWidth
        const scaleY = (root.height - padding * 2) / graphHeight
        root.scale = Math.min(scaleX, scaleY, 1.5)  // Cap at 1.5x

        // Center the graph
        root.offsetX = (root.width - graphWidth * root.scale) / 2 - minX * root.scale + padding
        root.offsetY = (root.height - graphHeight * root.scale) / 2 - minY * root.scale + padding
    }

    onWidthChanged: computeTransform()
    onHeightChanged: computeTransform()

    // Edges (rendered behind nodes)
    Repeater {
        model: workflowModel.edges

        Shape {
            id: edgeShape
            anchors.fill: parent

            ShapePath {
                strokeColor: Theme.edgeDefault
                strokeWidth: Theme.edgeWidth
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap

                // Start at first point
                startX: modelData.points.length > 0 ? modelData.points[0].x * root.scale + root.offsetX : 0
                startY: modelData.points.length > 0 ? modelData.points[0].y * root.scale + root.offsetY : 0

                // Draw path through remaining points
                PathPolyline {
                    path: {
                        let pts = []
                        for (let i = 0; i < modelData.points.length; i++) {
                            pts.push(Qt.point(
                                modelData.points[i].x * root.scale + root.offsetX,
                                modelData.points[i].y * root.scale + root.offsetY
                            ))
                        }
                        return pts
                    }
                }
            }

            // Arrow head at end (only render if we have valid points)
            Shape {
                id: arrowShape
                property bool hasValidPoints: modelData.points && modelData.points.length >= 2
                property var pts: hasValidPoints ? modelData.points : []
                property real lastX: pts.length >= 1 ? (pts[pts.length - 1].x || 0) : 0
                property real lastY: pts.length >= 1 ? (pts[pts.length - 1].y || 0) : 0
                property real prevX: pts.length >= 2 ? (pts[pts.length - 2].x || 0) : lastX
                property real prevY: pts.length >= 2 ? (pts[pts.length - 2].y || 0) : lastY
                property real arrowEndX: lastX * root.scale + root.offsetX
                property real arrowEndY: lastY * root.scale + root.offsetY
                property real arrowAngle: Math.atan2(lastY - prevY, lastX - prevX)

                visible: hasValidPoints

                ShapePath {
                    strokeColor: "transparent"
                    fillColor: Theme.edgeDefault

                    startX: arrowShape.arrowEndX
                    startY: arrowShape.arrowEndY

                    PathLine {
                        x: arrowShape.arrowEndX - 10 * Math.cos(arrowShape.arrowAngle - 0.4)
                        y: arrowShape.arrowEndY - 10 * Math.sin(arrowShape.arrowAngle - 0.4)
                    }
                    PathLine {
                        x: arrowShape.arrowEndX - 10 * Math.cos(arrowShape.arrowAngle + 0.4)
                        y: arrowShape.arrowEndY - 10 * Math.sin(arrowShape.arrowAngle + 0.4)
                    }
                    PathLine {
                        x: arrowShape.arrowEndX
                        y: arrowShape.arrowEndY
                    }
                }
            }
        }
    }

    // Nodes
    Repeater {
        model: workflowModel.nodes

        Rectangle {
            id: nodeRect
            x: modelData.x * root.scale + root.offsetX - width/2
            y: modelData.y * root.scale + root.offsetY - height/2
            width: Theme.nodeWidth
            height: Theme.nodeHeight
            radius: Theme.nodeRadius

            // Background color based on status
            color: {
                switch(modelData.status) {
                    case "current": return Theme.nodeCurrentBg
                    case "completed": return Theme.nodeCompletedBg
                    case "terminal": return Theme.nodeTerminalBg
                    default: return Theme.nodePendingBg
                }
            }

            // Border color based on status
            border.color: {
                switch(modelData.status) {
                    case "current": return Theme.nodeCurrentBorder
                    case "completed": return Theme.nodeCompletedBorder
                    case "terminal": return Theme.nodeTerminalBorder
                    default: return Theme.nodePendingBorder
                }
            }
            border.width: modelData.status === "current" ? 2 : 1

            // Selection highlight
            Rectangle {
                anchors.fill: parent
                anchors.margins: -3
                radius: parent.radius + 3
                color: "transparent"
                border.color: Theme.selectionHighlight
                border.width: 3
                visible: modelData.id === workflowModel.selectedPhase
            }

            // Node label
            Text {
                anchors.centerIn: parent
                text: modelData.label
                font.pixelSize: Theme.fontSizeMedium
                font.weight: modelData.status === "current" ? Font.Medium : Font.Normal
                color: Theme.textPrimary
                elide: Text.ElideMiddle
                width: parent.width - Theme.spacingMedium * 2
                horizontalAlignment: Text.AlignHCenter
            }

            // Status indicator dot
            Rectangle {
                width: 8
                height: 8
                radius: 4
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 8
                color: {
                    switch(modelData.status) {
                        case "current": return Theme.statusCurrent
                        case "completed": return Theme.statusCompleted
                        default: return "transparent"
                    }
                }
            }

            // Hover effect
            scale: mouseArea.containsMouse ? 1.03 : 1.0
            Behavior on scale { NumberAnimation { duration: Theme.animFast } }

            MouseArea {
                id: mouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: workflowModel.selectPhase(modelData.id)
            }
        }
    }

    // Empty state
    Text {
        anchors.centerIn: parent
        text: "No workflow phases"
        font.pixelSize: Theme.fontSizeLarge
        color: Theme.textMuted
        visible: workflowModel.nodes.length === 0
    }
}
