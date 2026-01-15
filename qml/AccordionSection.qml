import QtQuick
import QtQuick.Layouts
import "theme"

/**
 * AccordionSection - A collapsible panel with header and content.
 * Used for accordion-style layout in the sidebar.
 */
Item {
    id: root

    property string title: "Section"
    property string badge: ""
    property bool expanded: true
    property alias contentItem: contentContainer.children

    signal toggled()

    // Header height constant
    readonly property int headerHeight: 32

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
            onClicked: root.toggled()
        }
    }

    // Content container
    Item {
        id: contentContainer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        visible: root.expanded
        clip: true
    }
}
