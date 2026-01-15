import QtQuick
import QtQuick.Shapes
import "theme"

/**
 * Flowchart visualization of workflow phases.
 * Renders nodes and edges using Graphviz-computed positions.
 */
Item {
    id: root

    // Coordinate transformation - offset only, no scaling
    // Since node sizes are fixed in pixels, we just center the Graphviz layout
    property real scale: 1.0  // Fixed at 1.0 - no scaling
    property real offsetX: 50
    property real offsetY: 50

    // Compute offset to center graph on model change
    Component.onCompleted: computeTransform()
    Connections {
        target: workflowModel
        function onDataChanged() { computeTransform() }
    }

    function computeTransform() {
        if (workflowModel.nodes.length === 0) return

        // Find bounds of the graph
        let minX = Infinity, minY = Infinity
        let maxX = -Infinity, maxY = -Infinity

        for (let node of workflowModel.nodes) {
            // Use fixed node sizes from Theme for bounds calculation
            minX = Math.min(minX, node.x - Theme.nodeWidth/2)
            minY = Math.min(minY, node.y - Theme.nodeHeight/2)
            maxX = Math.max(maxX, node.x + Theme.nodeWidth/2)
            maxY = Math.max(maxY, node.y + Theme.nodeHeight/2)
        }

        // Calculate graph dimensions
        const graphWidth = maxX - minX
        const graphHeight = maxY - minY

        // Center the graph in the view
        root.offsetX = (root.width - graphWidth) / 2 - minX
        root.offsetY = (root.height - graphHeight) / 2 - minY
    }

    onWidthChanged: computeTransform()
    onHeightChanged: computeTransform()

    // Helper function to transform SVG path coordinates
    function transformSvgPath(path) {
        if (!path) return ""
        return path.replace(/(-?\d+\.?\d*),(-?\d+\.?\d*)/g, function(match, x, y) {
            let tx = parseFloat(x) * root.scale + root.offsetX
            let ty = parseFloat(y) * root.scale + root.offsetY
            return tx.toFixed(2) + "," + ty.toFixed(2)
        })
    }

    // Edge lines (rendered behind nodes) - use Graphviz cubic bezier splines
    Repeater {
        model: workflowModel.edges

        Shape {
            anchors.fill: parent
            visible: (modelData.svgPath || "").length > 0

            ShapePath {
                strokeColor: Theme.edgeDefault
                strokeWidth: Theme.edgeWidth
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap

                PathSvg {
                    path: root.transformSvgPath(modelData.svgPath || "")
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

    // Arrow heads (rendered on top of nodes)
    Repeater {
        model: workflowModel.edges

        Shape {
            id: arrowShape
            anchors.fill: parent

            property var arrowEnd: modelData.arrowEnd
            property var prevPoint: modelData.prevPoint
            property bool valid: arrowEnd !== null && arrowEnd !== undefined

            visible: valid

            ShapePath {
                id: arrowPath
                strokeColor: "transparent"
                fillColor: Theme.edgeDefault

                property real endX: arrowShape.valid ? arrowShape.arrowEnd.x * root.scale + root.offsetX : 0
                property real endY: arrowShape.valid ? arrowShape.arrowEnd.y * root.scale + root.offsetY : 0
                property real prevX: arrowShape.valid && arrowShape.prevPoint ? arrowShape.prevPoint.x * root.scale + root.offsetX : endX
                property real prevY: arrowShape.valid && arrowShape.prevPoint ? arrowShape.prevPoint.y * root.scale + root.offsetY : endY
                property real angle: arrowShape.valid ? Math.atan2(endY - prevY, endX - prevX) : 0
                property real arrowSize: 10

                startX: endX
                startY: endY

                PathLine {
                    x: arrowShape.valid ? arrowPath.endX - arrowPath.arrowSize * Math.cos(arrowPath.angle - 0.4) : 0
                    y: arrowShape.valid ? arrowPath.endY - arrowPath.arrowSize * Math.sin(arrowPath.angle - 0.4) : 0
                }
                PathLine {
                    x: arrowShape.valid ? arrowPath.endX - arrowPath.arrowSize * Math.cos(arrowPath.angle + 0.4) : 0
                    y: arrowShape.valid ? arrowPath.endY - arrowPath.arrowSize * Math.sin(arrowPath.angle + 0.4) : 0
                }
                PathLine {
                    x: arrowShape.valid ? arrowPath.endX : 0
                    y: arrowShape.valid ? arrowPath.endY : 0
                }
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
