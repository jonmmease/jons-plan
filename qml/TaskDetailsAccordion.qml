import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * Accordion component for displaying task details.
 * Shows collapsible sections for Prompt, Artifacts, Artifacts, and Logs.
 */
Rectangle {
    id: root
    color: Theme.bgPanel

    // Task data from workflowModel.selectedTask
    property var task: null

    // Section expansion states
    property bool promptExpanded: true
    property bool artifactsExpanded: false
    property bool findingsExpanded: false
    property bool logsExpanded: false

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 1

            // Task header
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: taskHeader.height + Theme.spacingSmall * 2
                color: Theme.bgPanelHeader

                ColumnLayout {
                    id: taskHeader
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Theme.spacingSmall
                    spacing: Theme.spacingTiny

                    Text {
                        text: root.task ? root.task.id : ""
                        font.pixelSize: Theme.fontSizeNormal
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.task ? root.task.description : ""
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                    }

                    // Badges row (status, model, type)
                    RowLayout {
                        spacing: Theme.spacingSmall

                        // Status badge
                        Rectangle {
                            width: statusText.width + Theme.spacingSmall * 2
                            height: statusText.height + Theme.spacingTiny * 2
                            radius: Theme.radiusSmall
                            color: {
                                if (!root.task) return Theme.nodePendingBg
                                switch(root.task.status) {
                                    case "in-progress": return Theme.nodeCurrentBg
                                    case "done": return Theme.nodeCompletedBg
                                    default: return Theme.nodePendingBg
                                }
                            }

                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                text: root.task ? root.task.status : "pending"
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textPrimary
                            }
                        }

                        // Model badge (if specified)
                        Rectangle {
                            visible: Boolean(root.task && root.task.model)
                            width: modelText.width + Theme.spacingSmall * 2
                            height: modelText.height + Theme.spacingTiny * 2
                            radius: Theme.radiusSmall
                            color: Theme.bgPanelHeader
                            border.width: 1
                            border.color: Theme.textMuted

                            Text {
                                id: modelText
                                anchors.centerIn: parent
                                text: root.task ? (root.task.model || "") : ""
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                            }
                        }

                        // Type badge (if specified)
                        Rectangle {
                            visible: Boolean(root.task && root.task.type)
                            width: typeText.width + Theme.spacingSmall * 2
                            height: typeText.height + Theme.spacingTiny * 2
                            radius: Theme.radiusSmall
                            color: root.task && root.task.type === "prototype" ? "#E8F5E9" : "#FFF3E0"
                            border.width: 1
                            border.color: root.task && root.task.type === "prototype" ? "#81C784" : "#FFB74D"

                            Text {
                                id: typeText
                                anchors.centerIn: parent
                                text: root.task ? (root.task.type || "") : ""
                                font.pixelSize: Theme.fontSizeSmall
                                color: root.task && root.task.type === "prototype" ? "#2E7D32" : "#E65100"
                            }
                        }
                    }

                    // Locks row (if task has locks)
                    RowLayout {
                        visible: Boolean(root.task && root.task.locks && root.task.locks.length > 0)
                        spacing: Theme.spacingSmall

                        Text {
                            text: "🔒 Locks:"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textMuted
                        }
                        Text {
                            text: root.task && root.task.locks ? root.task.locks.join(", ") : ""
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                        }
                    }

                    // Prototype question/hypothesis (only for prototype tasks)
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: Boolean(root.task && root.task.type === "prototype")
                        spacing: Theme.spacingTiny

                        // Question
                        RowLayout {
                            visible: Boolean(root.task && root.task.question)
                            spacing: Theme.spacingSmall

                            Text {
                                text: "Question:"
                                font.pixelSize: Theme.fontSizeSmall
                                font.weight: Font.Medium
                                color: Theme.textSecondary
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root.task ? (root.task.question || "") : ""
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textPrimary
                                wrapMode: Text.WordWrap
                            }
                        }

                        // Hypothesis
                        RowLayout {
                            visible: Boolean(root.task && root.task.hypothesis)
                            spacing: Theme.spacingSmall

                            Text {
                                text: "Hypothesis:"
                                font.pixelSize: Theme.fontSizeSmall
                                font.weight: Font.Medium
                                color: Theme.textSecondary
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root.task ? (root.task.hypothesis || "") : ""
                                font.pixelSize: Theme.fontSizeSmall
                                font.italic: true
                                color: Theme.textSecondary
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // Prompt section with Full/JSON toggle
            Rectangle {
                id: promptSection
                Layout.fillWidth: true
                Layout.preferredHeight: promptSection.promptExpanded ? promptContent.contentHeight + 32 + Theme.spacingSmall * 2 : 32
                color: Theme.bgPanel
                clip: true

                property bool promptExpanded: root.promptExpanded
                property bool showFullPrompt: false

                // Reset showFullPrompt when task changes
                Connections {
                    target: workflowModel
                    function onSelectedTaskChanged() {
                        promptSection.showFullPrompt = false
                    }
                }

                // Prompt header with toggle
                Rectangle {
                    id: promptHeader
                    width: parent.width
                    height: 32
                    color: promptHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                    MouseArea {
                        id: promptHeaderMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.promptExpanded = !root.promptExpanded
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingSmall
                        anchors.rightMargin: Theme.spacingSmall
                        spacing: Theme.spacingSmall

                        Text {
                            text: promptSection.promptExpanded ? "▼" : "▶"
                            font.pixelSize: 10
                            color: Theme.textMuted
                        }
                        Text {
                            text: "Prompt"
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }
                        Item { Layout.fillWidth: true }

                        // Full/JSON toggle button
                        Rectangle {
                            visible: workflowModel.selectedTaskId !== ""
                            width: promptToggleLabel.width + 16
                            height: 18
                            radius: 3
                            color: promptToggleMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                            border.width: 1
                            border.color: promptSection.showFullPrompt ? Theme.textLink : Theme.textMuted

                            Text {
                                id: promptToggleLabel
                                anchors.centerIn: parent
                                text: promptSection.showFullPrompt ? "JSON" : "Full"
                                font.pixelSize: 10
                                color: promptSection.showFullPrompt ? Theme.textLink : Theme.textSecondary
                            }
                            MouseArea {
                                id: promptToggleMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    promptSection.showFullPrompt = !promptSection.showFullPrompt
                                    if (promptSection.showFullPrompt && workflowModel.fullTaskPromptHtml === "") {
                                        workflowModel.loadFullTaskPrompt()
                                    }
                                }
                            }

                            ToolTip {
                                visible: promptToggleMouse.containsMouse
                                delay: 500
                                text: promptSection.showFullPrompt ?
                                    "Show task fields only" :
                                    "Show full assembled prompt (includes artifacts and parent outputs)"
                            }
                        }
                    }
                }

                TextEdit {
                    id: promptContent
                    anchors.top: promptHeader.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: Theme.spacingSmall
                    visible: promptSection.promptExpanded
                    text: Theme.wrapHtml(promptSection.showFullPrompt ?
                        workflowModel.fullTaskPromptHtml :
                        (workflowModel.selectedTaskPrompt || "<i>No prompt available</i>"), Theme.textSecondary)
                    textFormat: TextEdit.RichText
                    font.pixelSize: Theme.fontSizeSmall
                    wrapMode: Text.WordWrap
                    readOnly: true
                    selectByMouse: true
                    selectionColor: Theme.textLink
                }
            }

            // Artifacts section
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: findingsSection.expanded ? findingsContent.height + 32 + Theme.spacingSmall : 32
                color: Theme.bgPanel
                clip: true
                visible: (workflowModel.selectedTaskFindings || []).length > 0

                property bool expanded: root.findingsExpanded
                property var findings: workflowModel.selectedTaskFindings || []

                AccordionSection {
                    id: findingsSection
                    anchors.fill: parent
                    title: "Artifacts (" + parent.findings.length + ")"
                    expanded: parent.expanded
                    onToggled: root.findingsExpanded = !root.findingsExpanded

                    contentItem: [
                        ColumnLayout {
                            id: findingsContent
                            width: parent ? parent.width - Theme.spacingSmall * 2 : 100
                            x: Theme.spacingSmall
                            y: Theme.spacingTiny
                            spacing: 1

                            Repeater {
                                model: workflowModel.selectedTaskFindings || []
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: fileExpanded ? fileHeader.height + fileContentArea.height + 1 : fileHeader.height
                                    color: Theme.bgPanel
                                    clip: true

                                    property bool fileExpanded: true
                                    property bool showRichText: modelData.isHtml  // Default to rich if markdown

                                    // File header with name, copy button, expand toggle
                                    Rectangle {
                                        id: fileHeader
                                        width: parent.width
                                        height: 28
                                        color: fileHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                                        // Background click handler (lower z-order)
                                        MouseArea {
                                            id: fileHeaderMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: fileExpanded = !fileExpanded
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: Theme.spacingSmall
                                            anchors.rightMargin: Theme.spacingSmall
                                            spacing: Theme.spacingSmall

                                            // Expand indicator
                                            Text {
                                                text: fileExpanded ? "▼" : "▶"
                                                font.pixelSize: 10
                                                color: Theme.textMuted
                                            }

                                            // Filename
                                            Text {
                                                text: modelData.name
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.weight: Font.Medium
                                                color: Theme.textPrimary
                                                Layout.fillWidth: true
                                            }

                                            // Rich/Plain toggle (only for markdown files)
                                            Rectangle {
                                                visible: modelData.isHtml
                                                width: toggleLabel.width + Theme.spacingSmall * 2
                                                height: 20
                                                radius: Theme.radiusSmall
                                                color: toggleMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: toggleLabel
                                                    anchors.centerIn: parent
                                                    text: showRichText ? "Plain" : "Rich"
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    color: Theme.textSecondary
                                                }

                                                MouseArea {
                                                    id: toggleMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: showRichText = !showRichText
                                                }
                                            }

                                            // Open button
                                            Rectangle {
                                                width: openLabel.width + Theme.spacingSmall * 2
                                                height: 20
                                                radius: Theme.radiusSmall
                                                color: openMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: openLabel
                                                    anchors.centerIn: parent
                                                    text: "Open"
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    color: Theme.textSecondary
                                                }

                                                MouseArea {
                                                    id: openMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: workflowModel.openInEditor(modelData.filePath)
                                                }
                                            }

                                            // Copy button
                                            Rectangle {
                                                width: copyLabel.width + Theme.spacingSmall * 2
                                                height: 20
                                                radius: Theme.radiusSmall
                                                color: copyMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: copyLabel
                                                    anchors.centerIn: parent
                                                    text: "Copy"
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    color: Theme.textSecondary
                                                }

                                                MouseArea {
                                                    id: copyMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        workflowModel.copyToClipboard(modelData.rawContent || modelData.content)
                                                        copyLabel.text = "Copied!"
                                                        copyTimer.start()
                                                    }
                                                }

                                                Timer {
                                                    id: copyTimer
                                                    interval: 1500
                                                    onTriggered: copyLabel.text = "Copy"
                                                }
                                            }
                                        }
                                    }

                                    // File content (selectable)
                                    Rectangle {
                                        id: fileContentArea
                                        anchors.top: fileHeader.bottom
                                        anchors.topMargin: 1
                                        width: parent.width
                                        height: fileExpanded ? (showRichText ? richContentEdit.contentHeight : plainContentEdit.contentHeight) + Theme.spacingSmall * 2 : 0
                                        color: Theme.bgPanel
                                        visible: fileExpanded

                                        // Rich text view (rendered markdown)
                                        TextEdit {
                                            id: richContentEdit
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacingSmall
                                            visible: showRichText
                                            text: Theme.wrapHtml(modelData.content, Theme.textSecondary)
                                            textFormat: TextEdit.RichText
                                            font.pixelSize: Theme.fontSizeSmall
                                            wrapMode: Text.WordWrap
                                            readOnly: true
                                            selectByMouse: true
                                            selectionColor: Theme.textLink

                                            // Link click handler overlay
                                            MouseArea {
                                                anchors.fill: parent
                                                acceptedButtons: Qt.LeftButton
                                                cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor
                                                onClicked: function(mouse) {
                                                    var link = parent.linkAt(mouse.x, mouse.y)
                                                    if (link) {
                                                        if (!workflowModel.navigateToLink(link)) {
                                                            Qt.openUrlExternally(link)
                                                        }
                                                    } else {
                                                        mouse.accepted = false
                                                    }
                                                }
                                                onPressed: function(mouse) {
                                                    var link = parent.linkAt(mouse.x, mouse.y)
                                                    if (!link) {
                                                        mouse.accepted = false
                                                    }
                                                }
                                            }
                                        }

                                        // Plain text view (raw markdown)
                                        TextEdit {
                                            id: plainContentEdit
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacingSmall
                                            visible: !showRichText
                                            text: modelData.rawContent || modelData.content
                                            textFormat: TextEdit.PlainText
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: "Menlo"
                                            color: Theme.textSecondary
                                            wrapMode: Text.WordWrap
                                            readOnly: true
                                            selectByMouse: true
                                            selectionColor: Theme.textLink
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            }

            // Logs section
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: logsSection.expanded ? logsContent.contentHeight + 32 + Theme.spacingSmall * 2 : 32
                color: Theme.bgPanel
                clip: true

                property bool expanded: root.logsExpanded

                AccordionSection {
                    id: logsSection
                    anchors.fill: parent
                    title: "Logs"
                    expanded: parent.expanded
                    onToggled: root.logsExpanded = !root.logsExpanded

                    contentItem: [
                        TextEdit {
                            id: logsContent
                            width: parent ? parent.width - Theme.spacingSmall * 2 : 100
                            x: Theme.spacingSmall
                            y: Theme.spacingTiny
                            text: workflowModel.selectedTaskLogs || "(No logs yet)"
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: "Menlo"
                            color: Theme.textPrimary
                            wrapMode: Text.WordWrap
                            readOnly: true
                            selectByMouse: true
                            selectionColor: Theme.textLink
                        }
                    ]
                }
            }

            // Spacer
            Item {
                Layout.fillHeight: true
                Layout.minimumHeight: 10
            }
        }
    }
}
