import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

ApplicationWindow {
    id: root
    visible: true
    width: 1000
    height: 700
    minimumWidth: 600
    minimumHeight: 400
    title: "JonsPlan Viewer - " + workflowModel.planName

    color: Theme.bgWindow

    SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal

        // Left side: Flowchart
        Rectangle {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 300
            color: Theme.bgPanel

            Flowchart {
                id: flowchart
                anchors.fill: parent
                anchors.margins: Theme.spacingMedium
            }
        }

        // Right side: Details Panel
        Rectangle {
            SplitView.preferredWidth: Theme.detailsPanelWidth
            SplitView.minimumWidth: 250
            SplitView.maximumWidth: 500
            color: Theme.bgPanel

            DetailsPanel {
                id: detailsPanel
                anchors.fill: parent
            }
        }
    }

    // Bottom: Timeline Panel (collapsible)
    Rectangle {
        id: timelineContainer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: timelineExpanded ? Theme.timelinePanelHeight : timelineHeader.height
        color: Theme.bgTimeline

        Behavior on height {
            NumberAnimation { duration: Theme.animNormal }
        }

        property bool timelineExpanded: false

        // Timeline header
        Rectangle {
            id: timelineHeader
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
                    text: "Progress Timeline"
                    font.pixelSize: Theme.fontSizeNormal
                    font.weight: Font.Medium
                    color: Theme.textPrimary
                }

                Text {
                    text: "(" + workflowModel.progressEntries.length + " entries)"
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: timelineContainer.timelineExpanded ? "Hide" : "Show"
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textLink

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: timelineContainer.timelineExpanded = !timelineContainer.timelineExpanded
                    }
                }
            }
        }

        // Timeline content
        TimelinePanel {
            id: timelinePanel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: timelineHeader.bottom
            anchors.bottom: parent.bottom
            visible: timelineContainer.timelineExpanded
        }
    }
}
