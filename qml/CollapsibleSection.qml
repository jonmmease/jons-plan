import QtQuick
import QtQuick.Layouts
import "theme"

/**
 * CollapsibleSection - A panel with a clickable header that expands/collapses content.
 * Used for accordion-style layout in the left sidebar.
 */
Item {
    id: root

    property string title: "Section"
    property string badge: ""
    property bool expanded: true
    property alias content: contentLoader.sourceComponent

    // Minimum height when collapsed (just header)
    readonly property int headerHeight: 32

    // Height when expanded includes header + content
    implicitHeight: expanded ? headerHeight + contentLoader.height : headerHeight

    Behavior on implicitHeight {
        NumberAnimation { duration: Theme.animNormal }
    }

    // Header
    Rectangle {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.headerHeight
        color: headerMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingSmall
            anchors.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            // Expand/collapse indicator
            Text {
                text: root.expanded ? "▼" : "▶"
                font.pixelSize: 10
                color: Theme.textMuted
            }

            Text {
                text: root.title
                font.pixelSize: Theme.fontSizeNormal
                font.weight: Font.Medium
                color: Theme.textPrimary
            }

            Text {
                visible: root.badge !== ""
                text: root.badge
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            Item { Layout.fillWidth: true }
        }

        MouseArea {
            id: headerMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.expanded = !root.expanded
        }
    }

    // Content (loaded via Loader to allow default component)
    Loader {
        id: contentLoader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        visible: root.expanded
        height: visible ? item.implicitHeight : 0
        clip: true
    }
}
