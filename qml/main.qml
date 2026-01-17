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

    // Bind theme to model
    Binding {
        target: Theme
        property: "isDark"
        value: workflowModel.isDark
    }

    // Track which sections are expanded
    property bool flowchartExpanded: true
    property bool requestExpanded: false  // Request accordion collapsed by default
    property bool historyExpanded: true
    property bool timelineExpanded: false

    // Computed: are all panels collapsed?
    property bool allCollapsed: !flowchartExpanded && !requestExpanded && !historyExpanded && !timelineExpanded

    // Header height for collapsed sections
    readonly property int sectionHeaderHeight: 32

    // Collapsed sidebar width
    readonly property int collapsedSidebarWidth: 36

    // Theme toggle button (floating, top-right)
    Rectangle {
        id: themeToggle
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Theme.spacingSmall
        z: 100  // Float above everything
        width: 28
        height: 28
        radius: Theme.radiusSmall
        color: themeToggleMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader
        border.width: 1
        border.color: Theme.borderLight

        Text {
            anchors.centerIn: parent
            text: {
                switch(workflowModel.themeMode) {
                    case "light": return "☀"
                    case "dark": return "☾"
                    default: return "◐"  // system
                }
            }
            font.pixelSize: 14
            color: Theme.textPrimary
        }

        MouseArea {
            id: themeToggleMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: workflowModel.cycleTheme()
        }

        ToolTip {
            visible: themeToggleMouse.containsMouse
            delay: 500
            text: {
                switch(workflowModel.themeMode) {
                    case "light": return "Light mode (click to switch)"
                    case "dark": return "Dark mode (click to switch)"
                    default: return "System theme (click to switch)"
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Collapsed sidebar (shown when all panels collapsed)
        Rectangle {
            Layout.preferredWidth: root.collapsedSidebarWidth
            Layout.fillHeight: true
            visible: root.allCollapsed
            color: Theme.bgPanelHeader

            ColumnLayout {
                anchors.fill: parent
                spacing: 1

                // Workflow button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: flowchartBtn.containsMouse ? Theme.hoverHighlight : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "Workflow"
                        rotation: -90
                        font.pixelSize: Theme.fontSizeSmall
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        id: flowchartBtn
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.flowchartExpanded = true
                    }
                }

                // Request button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: requestBtn.containsMouse ? Theme.hoverHighlight : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "Request"
                        rotation: -90
                        font.pixelSize: Theme.fontSizeSmall
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        id: requestBtn
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.requestExpanded = true
                    }
                }

                // History button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: historyBtn.containsMouse ? Theme.hoverHighlight : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "History"
                        rotation: -90
                        font.pixelSize: Theme.fontSizeSmall
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        id: historyBtn
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.historyExpanded = true
                    }
                }

                // Timeline button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: timelineBtn.containsMouse ? Theme.hoverHighlight : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "Timeline"
                        rotation: -90
                        font.pixelSize: Theme.fontSizeSmall
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        id: timelineBtn
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.timelineExpanded = true
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // Main content area
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            // Left side: Vertical SplitView with panels (hidden when all collapsed)
            SplitView {
                SplitView.fillWidth: false
                SplitView.preferredWidth: root.allCollapsed ? 0 : 450
                SplitView.minimumWidth: root.allCollapsed ? 0 : 200
                visible: !root.allCollapsed
                orientation: Qt.Vertical

                // Section 1: Workflow Diagram
                Rectangle {
                    SplitView.fillHeight: root.flowchartExpanded
                    SplitView.minimumHeight: root.sectionHeaderHeight
                    SplitView.preferredHeight: root.flowchartExpanded ? 300 : root.sectionHeaderHeight
                    color: Theme.bgPanel
                    clip: true

                    // Header
                    Rectangle {
                        id: flowchartHeader
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: root.sectionHeaderHeight
                        color: flowchartHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader
                        z: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingMedium
                            spacing: Theme.spacingSmall

                            Text {
                                text: root.flowchartExpanded ? "▼" : "▶"
                                font.pixelSize: 10
                                color: Theme.textMuted
                            }

                            Text {
                                text: "Workflow Diagram"
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.Medium
                                color: Theme.textPrimary
                            }

                            Item { Layout.fillWidth: true }
                        }

                        MouseArea {
                            id: flowchartHeaderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.flowchartExpanded = !root.flowchartExpanded
                        }
                    }

                    // Scrollable flowchart content
                    Flickable {
                        id: flowchartFlickable
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: flowchartHeader.bottom
                        anchors.bottom: parent.bottom
                        visible: root.flowchartExpanded
                        clip: true
                        contentWidth: Math.max(flowchart.minContentWidth, width)
                        contentHeight: Math.max(flowchart.minContentHeight, height)
                        boundsBehavior: Flickable.StopAtBounds

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }

                        Flowchart {
                            id: flowchart
                            width: flowchartFlickable.contentWidth
                            height: flowchartFlickable.contentHeight
                        }
                    }
                }

                // Section 2: Request (collapsed by default)
                Rectangle {
                    SplitView.fillHeight: root.requestExpanded && !root.flowchartExpanded
                    SplitView.minimumHeight: root.sectionHeaderHeight
                    SplitView.preferredHeight: root.requestExpanded ? 200 : root.sectionHeaderHeight
                    color: Theme.bgPanel
                    clip: true

                    // Header
                    Rectangle {
                        id: requestHeader
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: root.sectionHeaderHeight
                        color: requestHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader
                        z: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingMedium
                            spacing: Theme.spacingSmall

                            Text {
                                text: root.requestExpanded ? "▼" : "▶"
                                font.pixelSize: 10
                                color: Theme.textMuted
                            }

                            Text {
                                text: "Request"
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.Medium
                                color: Theme.textPrimary
                            }

                            Item { Layout.fillWidth: true }
                        }

                        MouseArea {
                            id: requestHeaderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.requestExpanded = !root.requestExpanded
                        }
                    }

                    // Request content
                    ScrollView {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: requestHeader.bottom
                        anchors.bottom: parent.bottom
                        visible: root.requestExpanded
                        clip: true

                        Text {
                            width: parent.width - Theme.spacingMedium * 2
                            x: Theme.spacingMedium
                            y: Theme.spacingSmall
                            text: workflowModel.requestHtml
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeNormal
                            lineHeight: 1.4
                        }
                    }
                }

                // Section 3: Phase History
                Rectangle {
                    SplitView.fillHeight: root.historyExpanded && !root.flowchartExpanded && !root.requestExpanded
                    SplitView.minimumHeight: root.sectionHeaderHeight
                    SplitView.preferredHeight: root.historyExpanded ? 200 : root.sectionHeaderHeight
                    color: Theme.bgPanel
                    clip: true

                    // Header
                    Rectangle {
                        id: historyHeader
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: root.sectionHeaderHeight
                        color: historyHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader
                        z: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingMedium
                            spacing: Theme.spacingSmall

                            Text {
                                text: root.historyExpanded ? "▼" : "▶"
                                font.pixelSize: 10
                                color: Theme.textMuted
                            }

                            Text {
                                text: "Phase History"
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.Medium
                                color: Theme.textPrimary
                            }

                            Text {
                                text: "(" + workflowModel.phaseHistory.length + ")"
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                            }

                            Item { Layout.fillWidth: true }
                        }

                        MouseArea {
                            id: historyHeaderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.historyExpanded = !root.historyExpanded
                        }
                    }

                    // Phase history list
                    PhaseHistoryList {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: historyHeader.bottom
                        anchors.bottom: parent.bottom
                        visible: root.historyExpanded
                    }
                }

                // Section 3: Progress Timeline
                Rectangle {
                    SplitView.fillHeight: root.timelineExpanded && !root.flowchartExpanded && !root.historyExpanded
                    SplitView.minimumHeight: root.sectionHeaderHeight
                    SplitView.preferredHeight: root.timelineExpanded ? 150 : root.sectionHeaderHeight
                    color: Theme.bgTimeline
                    clip: true

                    // Header
                    Rectangle {
                        id: timelineHeader
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: root.sectionHeaderHeight
                        color: timelineHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader
                        z: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingMedium
                            spacing: Theme.spacingSmall

                            Text {
                                text: root.timelineExpanded ? "▼" : "▶"
                                font.pixelSize: 10
                                color: Theme.textMuted
                            }

                            Text {
                                text: "Progress Timeline"
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.Medium
                                color: Theme.textPrimary
                            }

                            Text {
                                text: "(" + workflowModel.progressEntries.length + ")"
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                            }

                            Item { Layout.fillWidth: true }
                        }

                        MouseArea {
                            id: timelineHeaderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.timelineExpanded = !root.timelineExpanded
                        }
                    }

                    // Timeline content
                    TimelinePanel {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: timelineHeader.bottom
                        anchors.bottom: parent.bottom
                        visible: root.timelineExpanded
                    }
                }
            }

            // Right side: Details Panel
            Rectangle {
                SplitView.fillWidth: true
                SplitView.preferredWidth: Theme.detailsPanelWidth
                SplitView.minimumWidth: 300
                color: Theme.bgPanel

                DetailsPanel {
                    id: detailsPanel
                    anchors.fill: parent
                }
            }
        }
    }
}
