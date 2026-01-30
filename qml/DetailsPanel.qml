import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"

/**
 * Details panel showing information about the selected phase and tasks.
 * Two tabs: Phase (prompt/artifacts) and Tasks (tree + details accordion).
 */
Rectangle {
    id: root
    color: Theme.bgPanel

    // Track the last selected phase to detect actual phase changes
    property string lastSelectedPhase: ""

    // Connect to tab switch signal from model
    Connections {
        target: workflowModel
        function onRequestTabSwitch(tabIndex) {
            tabBar.currentIndex = tabIndex
        }
        function onSelectedPhaseChanged() {
            // Only switch to Phase tab when a DIFFERENT phase is selected,
            // not when the same phase's details are updated during reload
            if (workflowModel.selectedPhase !== root.lastSelectedPhase) {
                root.lastSelectedPhase = workflowModel.selectedPhase
                tabBar.currentIndex = 0
            }
        }
    }

    // Empty state when no phase selected
    Text {
        anchors.centerIn: parent
        text: "Select a phase to view details"
        font.pixelSize: Theme.fontSizeNormal
        color: Theme.textMuted
        visible: workflowModel.selectedPhase === ""
    }

    // Main content when phase is selected
    ColumnLayout {
        anchors.fill: parent
        visible: workflowModel.selectedPhase !== ""
        spacing: 0

        // Header with phase name and status
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

                    // Entry badge
                    Rectangle {
                        visible: workflowModel.selectedPhaseEntry > 0
                        width: entryText.width + Theme.spacingSmall * 2
                        height: entryText.height + Theme.spacingTiny * 2
                        radius: Theme.radiusSmall
                        color: Theme.bgPanelHeader
                        border.width: 1
                        border.color: Theme.nodePendingBorder

                        Text {
                            id: entryText
                            anchors.centerIn: parent
                            text: "Entry #" + String(workflowModel.selectedPhaseEntry).padStart(2, "0")
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }
                    }

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

                    // Outcome badge (if phase completed)
                    Rectangle {
                        visible: Boolean(workflowModel.selectedPhaseDetails.outcome)
                        width: outcomeText.width + Theme.spacingSmall * 2
                        height: outcomeText.height + Theme.spacingTiny * 2
                        radius: Theme.radiusSmall
                        color: workflowModel.selectedPhaseDetails.outcome === "completed" ? "#E8F5E9" : "#FFF3E0"
                        border.width: 1
                        border.color: workflowModel.selectedPhaseDetails.outcome === "completed" ? "#81C784" : "#FFB74D"

                        Text {
                            id: outcomeText
                            anchors.centerIn: parent
                            text: workflowModel.selectedPhaseDetails.outcome || ""
                            font.pixelSize: Theme.fontSizeSmall
                            color: workflowModel.selectedPhaseDetails.outcome === "completed" ? "#2E7D32" : "#E65100"
                        }
                    }
                }

                // Timestamps metadata row (subtle, small text)
                Text {
                    visible: Boolean(workflowModel.selectedPhaseDetails.entered)
                    font.pixelSize: Theme.fontSizeSmall - 1
                    color: Theme.textMuted

                    function formatTimestamp(isoStr) {
                        if (!isoStr) return ""
                        try {
                            var d = new Date(isoStr)
                            return d.toLocaleDateString(Qt.locale(), "MMM d") + " " +
                                   d.toLocaleTimeString(Qt.locale(), "HH:mm")
                        } catch (e) {
                            return isoStr.split("T")[0]
                        }
                    }

                    function formatDuration(entered, exited) {
                        if (!entered || !exited) return ""
                        try {
                            var start = new Date(entered)
                            var end = new Date(exited)
                            var diffMs = end - start
                            var diffMins = Math.floor(diffMs / 60000)
                            var diffSecs = Math.floor((diffMs % 60000) / 1000)
                            if (diffMins > 60) {
                                var hours = Math.floor(diffMins / 60)
                                var mins = diffMins % 60
                                return hours + "h " + mins + "m"
                            }
                            return diffMins + "m " + diffSecs + "s"
                        } catch (e) {
                            return ""
                        }
                    }

                    text: {
                        var entered = workflowModel.selectedPhaseDetails.entered
                        var exited = workflowModel.selectedPhaseDetails.exited
                        var parts = []
                        if (entered) parts.push("Entered: " + formatTimestamp(entered))
                        if (exited) parts.push("Duration: " + formatDuration(entered, exited))
                        return parts.join("  |  ")
                    }
                }
            }
        }

        // Separator line above tabs
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.borderLight
        }

        // Tab bar with navigation buttons
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: tabRowLayout.implicitHeight
            color: Theme.bgPanelHeader

            RowLayout {
                id: tabRowLayout
                anchors.fill: parent
                spacing: 0

                TabBar {
                id: tabBar
                Layout.fillWidth: true
                background: Rectangle { color: Theme.bgPanelHeader }

            TabButton {
                text: "Phase"
                width: implicitWidth
                padding: 8
                background: Rectangle {
                    color: tabBar.currentIndex === 0 ? Theme.bgPanel : Theme.bgPanelHeader
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 2
                        color: Theme.textLink
                        visible: tabBar.currentIndex === 0
                    }
                }
                contentItem: Text {
                    text: parent.text
                    font.pixelSize: Theme.fontSizeNormal
                    font.weight: tabBar.currentIndex === 0 ? Font.DemiBold : Font.Normal
                    color: tabBar.currentIndex === 0 ? Theme.textLink : Theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            TabButton {
                visible: Boolean(workflowModel.selectedPhaseDetails.use_tasks)
                text: "Tasks" + ((workflowModel.selectedPhaseDetails.tasks || []).length > 0 ?
                      " (" + (workflowModel.selectedPhaseDetails.tasks || []).length + ")" : "")
                width: visible ? implicitWidth : 0
                padding: 8
                background: Rectangle {
                    color: tabBar.currentIndex === 1 ? Theme.bgPanel : Theme.bgPanelHeader
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 2
                        color: Theme.textLink
                        visible: tabBar.currentIndex === 1
                    }
                }
                contentItem: Text {
                    text: parent.text
                    font.pixelSize: Theme.fontSizeNormal
                    font.weight: tabBar.currentIndex === 1 ? Font.DemiBold : Font.Normal
                    color: tabBar.currentIndex === 1 ? Theme.textLink : Theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            }

            // Navigation buttons (inline with tabs)
            Row {
                Layout.alignment: Qt.AlignVCenter
                Layout.rightMargin: Theme.spacingSmall
                visible: workflowModel.selectedPhaseEntry > 0
                spacing: Theme.spacingSmall

                Rectangle {
                    width: 28
                    height: 28
                    radius: Theme.radiusSmall
                    color: prevMouse.containsMouse && prevMouse.enabled ? Theme.hoverHighlight : "transparent"
                    border.width: 1
                    border.color: prevMouse.containsMouse && prevMouse.enabled ? Theme.borderLight : "transparent"
                    opacity: workflowModel.selectedPhaseEntry > 1 ? 1 : 0.4

                    Text {
                        anchors.centerIn: parent
                        text: "‹"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: workflowModel.selectedPhaseEntry > 1 ? Theme.textLink : Theme.textMuted
                    }

                    MouseArea {
                        id: prevMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: workflowModel.selectedPhaseEntry > 1
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: workflowModel.selectPhaseEntry(workflowModel.selectedPhaseEntry - 1)
                    }
                }

                Rectangle {
                    width: 28
                    height: 28
                    radius: Theme.radiusSmall
                    color: nextMouse.containsMouse && nextMouse.enabled ? Theme.hoverHighlight : "transparent"
                    border.width: 1
                    border.color: nextMouse.containsMouse && nextMouse.enabled ? Theme.borderLight : "transparent"
                    opacity: workflowModel.selectedPhaseEntry < workflowModel.phaseHistory.length ? 1 : 0.4

                    Text {
                        anchors.centerIn: parent
                        text: "›"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: workflowModel.selectedPhaseEntry < workflowModel.phaseHistory.length ? Theme.textLink : Theme.textMuted
                    }

                    MouseArea {
                        id: nextMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: workflowModel.selectedPhaseEntry < workflowModel.phaseHistory.length
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: workflowModel.selectPhaseEntry(workflowModel.selectedPhaseEntry + 1)
                    }
                }
            }
            }
        }

        // Tab content
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // Phase tab content
            ScrollView {
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: 1

                    // Entry reason (if present)
                    Rectangle {
                        id: reasonSection
                        Layout.fillWidth: true
                        Layout.preferredHeight: reasonExpanded ? reasonContent.height + 28 + Theme.spacingSmall : 28
                        color: Theme.bgPanel
                        clip: true
                        visible: (workflowModel.selectedPhaseDetails.reason || "") !== ""

                        property bool reasonExpanded: true

                        // Reset expanded state when phase changes (to default: expanded)
                        Connections {
                            target: workflowModel
                            function onSelectedPhaseChanged() {
                                reasonSection.reasonExpanded = true
                            }
                        }

                        Rectangle {
                            id: reasonHeader
                            width: parent.width
                            height: 28
                            color: reasonHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                            MouseArea {
                                id: reasonHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.parent.reasonExpanded = !parent.parent.reasonExpanded
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSmall
                                anchors.rightMargin: Theme.spacingSmall

                                Text {
                                    text: parent.parent.parent.reasonExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                }
                                Text {
                                    text: "Entry Reason"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }

                        TextEdit {
                            id: reasonContent
                            anchors.top: reasonHeader.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: Theme.spacingSmall
                            text: workflowModel.selectedPhaseDetails.reason || ""
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textPrimary
                            wrapMode: Text.WordWrap
                            readOnly: true
                            selectByMouse: true
                        }
                    }

                    // Artifact Contract section (inputs/outputs from workflow.toml)
                    Rectangle {
                        id: artifactContractSection
                        Layout.fillWidth: true
                        Layout.preferredHeight: artifactContractExpanded ? artifactContractContent.height + 28 + Theme.spacingSmall : 28
                        color: Theme.bgPanel
                        clip: true
                        visible: (workflowModel.selectedPhaseDetails.context_artifacts || []).length > 0 ||
                                 (workflowModel.selectedPhaseDetails.required_artifacts || []).length > 0

                        property bool artifactContractExpanded: true

                        // Reset expanded state when phase changes (to default: expanded)
                        Connections {
                            target: workflowModel
                            function onSelectedPhaseChanged() {
                                artifactContractSection.artifactContractExpanded = true
                            }
                        }

                        Rectangle {
                            id: artifactContractHeader
                            width: parent.width
                            height: 28
                            color: artifactContractHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                            MouseArea {
                                id: artifactContractHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.parent.artifactContractExpanded = !parent.parent.artifactContractExpanded
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSmall
                                anchors.rightMargin: Theme.spacingSmall

                                Text {
                                    text: parent.parent.parent.artifactContractExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                }
                                Text {
                                    text: "Artifact Contract"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }

                        ColumnLayout {
                            id: artifactContractContent
                            anchors.top: artifactContractHeader.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: Theme.spacingSmall
                            spacing: Theme.spacingSmall

                            // Context artifacts (inputs)
                            RowLayout {
                                visible: (workflowModel.selectedPhaseDetails.context_artifacts || []).length > 0
                                spacing: Theme.spacingSmall

                                Text {
                                    text: "Inputs:"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textSecondary
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacingTiny

                                    Repeater {
                                        model: workflowModel.selectedPhaseDetails.context_artifacts || []
                                        delegate: Rectangle {
                                            width: inputArtifactText.width + Theme.spacingSmall * 2
                                            height: inputArtifactText.height + Theme.spacingTiny * 2
                                            radius: Theme.radiusSmall
                                            color: "#E3F2FD"
                                            border.width: 1
                                            border.color: "#90CAF9"

                                            Text {
                                                id: inputArtifactText
                                                anchors.centerIn: parent
                                                text: modelData
                                                font.pixelSize: Theme.fontSizeSmall
                                                color: "#1565C0"
                                            }
                                        }
                                    }
                                }
                            }

                            // Required artifacts (outputs)
                            RowLayout {
                                visible: (workflowModel.selectedPhaseDetails.required_artifacts || []).length > 0
                                spacing: Theme.spacingSmall

                                Text {
                                    text: "Outputs:"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textSecondary
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacingTiny

                                    Repeater {
                                        model: workflowModel.selectedPhaseDetails.required_artifacts || []
                                        delegate: Rectangle {
                                            width: outputArtifactText.width + Theme.spacingSmall * 2
                                            height: outputArtifactText.height + Theme.spacingTiny * 2
                                            radius: Theme.radiusSmall
                                            color: "#E8F5E9"
                                            border.width: 1
                                            border.color: "#A5D6A7"

                                            Text {
                                                id: outputArtifactText
                                                anchors.centerIn: parent
                                                text: modelData
                                                font.pixelSize: Theme.fontSizeSmall
                                                color: "#2E7D32"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Phase Prompt section
                    Rectangle {
                        id: promptSection
                        Layout.fillWidth: true
                        Layout.preferredHeight: promptExpanded ? promptContentEdit.contentHeight + 28 + Theme.spacingSmall * 2 : 28
                        color: Theme.bgPanel
                        clip: true

                        property bool promptExpanded: true
                        property bool showFullPrompt: false

                        // Reset showFullPrompt when phase changes
                        Connections {
                            target: workflowModel
                            function onSelectedPhaseChanged() {
                                promptSection.showFullPrompt = false
                            }
                        }

                        Rectangle {
                            id: promptHeader
                            width: parent.width
                            height: 28
                            color: promptHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                            MouseArea {
                                id: promptHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: promptSection.promptExpanded = !promptSection.promptExpanded
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSmall
                                anchors.rightMargin: Theme.spacingSmall

                                Text {
                                    text: promptSection.promptExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                }
                                Text {
                                    text: "Phase Prompt"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                }
                                Item { Layout.fillWidth: true }

                                // Full/TOML toggle button
                                Rectangle {
                                    visible: workflowModel.selectedPhaseEntry > 0
                                    width: promptToggleLabel.width + 16
                                    height: 18
                                    radius: 3
                                    color: promptToggleMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                    border.width: 1
                                    border.color: promptSection.showFullPrompt ? Theme.textLink : Theme.textMuted

                                    Text {
                                        id: promptToggleLabel
                                        anchors.centerIn: parent
                                        text: promptSection.showFullPrompt ? "TOML" : "Full"
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
                                            if (promptSection.showFullPrompt && workflowModel.fullPhasePromptHtml === "") {
                                                workflowModel.loadFullPhasePrompt()
                                            }
                                        }
                                    }

                                    ToolTip {
                                        visible: promptToggleMouse.containsMouse
                                        delay: 500
                                        text: promptSection.showFullPrompt ?
                                            "Show TOML prompt only" :
                                            "Show full assembled prompt (includes artifacts and guidance)"
                                    }
                                }
                            }
                        }

                        TextEdit {
                            id: promptContentEdit
                            anchors.top: promptHeader.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: Theme.spacingSmall
                            text: Theme.wrapHtml(promptSection.showFullPrompt ?
                                workflowModel.fullPhasePromptHtml :
                                workflowModel.selectedPhasePromptHtml)
                            textFormat: TextEdit.RichText
                            font.pixelSize: Theme.fontSizeSmall
                            wrapMode: Text.WordWrap
                            readOnly: true
                            selectByMouse: true
                        }
                    }

                    // Artifacts section
                    Rectangle {
                        id: artifactsSection
                        Layout.fillWidth: true
                        Layout.preferredHeight: artifactsExpanded ? artifactsContent.height + 28 + Theme.spacingSmall : 28
                        color: Theme.bgPanel
                        clip: true
                        visible: (workflowModel.selectedPhaseArtifacts || []).length > 0

                        property bool artifactsExpanded: false

                        // Reset expanded state when phase changes
                        Connections {
                            target: workflowModel
                            function onSelectedPhaseChanged() {
                                artifactsSection.artifactsExpanded = false
                            }
                        }

                        Rectangle {
                            id: artifactsHeader
                            width: parent.width
                            height: 28
                            color: artifactsHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                            MouseArea {
                                id: artifactsHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.parent.artifactsExpanded = !parent.parent.artifactsExpanded
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSmall
                                anchors.rightMargin: Theme.spacingSmall

                                Text {
                                    text: parent.parent.parent.artifactsExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                }
                                Text {
                                    text: "Artifacts (" + (workflowModel.selectedPhaseArtifacts || []).length + ")"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }

                        ColumnLayout {
                            id: artifactsContent
                            anchors.top: artifactsHeader.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: Theme.spacingSmall
                            spacing: 1

                            Repeater {
                                model: workflowModel.selectedPhaseArtifacts || []
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: artFileExpanded ? artFileHeader.height + artFileContent.height + 1 : artFileHeader.height
                                    color: Theme.bgPanel
                                    clip: true

                                    property bool artFileExpanded: false
                                    property bool showRichText: modelData.isHtml

                                    Rectangle {
                                        id: artFileHeader
                                        width: parent.width
                                        height: 24
                                        color: artFileMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                                        MouseArea {
                                            id: artFileMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: artFileExpanded = !artFileExpanded
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: Theme.spacingSmall
                                            anchors.rightMargin: Theme.spacingSmall
                                            spacing: Theme.spacingSmall

                                            Text {
                                                text: artFileExpanded ? "▼" : "▶"
                                                font.pixelSize: 10
                                                color: Theme.textMuted
                                            }
                                            Text {
                                                text: modelData.name
                                                font.pixelSize: Theme.fontSizeSmall
                                                color: Theme.textPrimary
                                                Layout.fillWidth: true
                                            }

                                            Rectangle {
                                                visible: modelData.isHtml
                                                width: artToggleLabel.width + 8
                                                height: 18
                                                radius: 3
                                                color: artToggleMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: artToggleLabel
                                                    anchors.centerIn: parent
                                                    text: showRichText ? "Plain" : "Rich"
                                                    font.pixelSize: 10
                                                    color: Theme.textSecondary
                                                }
                                                MouseArea {
                                                    id: artToggleMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: showRichText = !showRichText
                                                }
                                            }

                                            Rectangle {
                                                width: artOpenLabel.width + 8
                                                height: 18
                                                radius: 3
                                                color: artOpenMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: artOpenLabel
                                                    anchors.centerIn: parent
                                                    text: "Open"
                                                    font.pixelSize: 10
                                                    color: Theme.textSecondary
                                                }
                                                MouseArea {
                                                    id: artOpenMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: workflowModel.openInEditor(modelData.filePath)
                                                }
                                            }

                                            Rectangle {
                                                width: artCopyLabel.width + 8
                                                height: 18
                                                radius: 3
                                                color: artCopyMouse.containsMouse ? Theme.bgPanelHeader : "transparent"
                                                border.width: 1
                                                border.color: Theme.textMuted

                                                Text {
                                                    id: artCopyLabel
                                                    anchors.centerIn: parent
                                                    text: "Copy"
                                                    font.pixelSize: 10
                                                    color: Theme.textSecondary
                                                }
                                                MouseArea {
                                                    id: artCopyMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        workflowModel.copyToClipboard(modelData.rawContent || modelData.content)
                                                        artCopyLabel.text = "Copied!"
                                                        artCopyTimer.start()
                                                    }
                                                }
                                                Timer {
                                                    id: artCopyTimer
                                                    interval: 1500
                                                    onTriggered: artCopyLabel.text = "Copy"
                                                }
                                            }
                                        }
                                    }

                                    Rectangle {
                                        id: artFileContent
                                        anchors.top: artFileHeader.bottom
                                        width: parent.width
                                        height: artFileExpanded ? (showRichText ? artRichEdit.contentHeight : artPlainEdit.contentHeight) + Theme.spacingSmall * 2 : 0
                                        color: Theme.bgPanel
                                        visible: artFileExpanded

                                        TextEdit {
                                            id: artRichEdit
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacingSmall
                                            visible: showRichText
                                            text: Theme.wrapHtml(modelData.content)
                                            textFormat: TextEdit.RichText
                                            font.pixelSize: Theme.fontSizeSmall
                                            wrapMode: Text.WordWrap
                                            readOnly: true
                                            selectByMouse: true

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
                                                        // Pass through for text selection
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
                                        TextEdit {
                                            id: artPlainEdit
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacingSmall
                                            visible: !showRichText
                                            text: modelData.rawContent || modelData.content
                                            textFormat: TextEdit.PlainText
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: "Menlo"
                                            color: Theme.textPrimary
                                            wrapMode: Text.WordWrap
                                            readOnly: true
                                            selectByMouse: true
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Logs section
                    Rectangle {
                        id: logsSection
                        Layout.fillWidth: true
                        Layout.preferredHeight: logsExpanded ? 200 : 28
                        color: Theme.bgPanel
                        clip: true
                        visible: (workflowModel.selectedPhaseLogs || "") !== ""

                        property bool logsExpanded: false

                        // Reset expanded state when phase changes
                        Connections {
                            target: workflowModel
                            function onSelectedPhaseChanged() {
                                logsSection.logsExpanded = false
                            }
                        }

                        Rectangle {
                            id: logsHeader
                            width: parent.width
                            height: 28
                            color: logsHeaderMouse.containsMouse ? Theme.hoverHighlight : Theme.bgPanelHeader

                            MouseArea {
                                id: logsHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.parent.logsExpanded = !parent.parent.logsExpanded
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSmall
                                anchors.rightMargin: Theme.spacingSmall

                                Text {
                                    text: parent.parent.parent.logsExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                }
                                Text {
                                    text: "Logs"
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }

                        ScrollView {
                            anchors.top: logsHeader.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: Theme.spacingSmall
                            clip: true
                            visible: parent.logsExpanded

                            TextEdit {
                                width: parent.width
                                text: workflowModel.selectedPhaseLogs || ""
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: "Menlo"
                                color: Theme.textPrimary
                                wrapMode: Text.WordWrap
                                readOnly: true
                                selectByMouse: true
                            }
                        }
                    }
                }
            }

            // Tasks tab content
            Item {
                // Check if there are tasks
                property var tasks: workflowModel.selectedPhaseDetails.tasks || []
                property bool hasTasks: tasks.length > 0

                // Empty state when no tasks
                Text {
                    anchors.centerIn: parent
                    text: "No tasks in this phase"
                    font.pixelSize: Theme.fontSizeNormal
                    color: Theme.textMuted
                    visible: !parent.hasTasks
                }

                // Tasks content when tasks exist
                SplitView {
                    anchors.fill: parent
                    orientation: Qt.Vertical
                    visible: parent.hasTasks

                    // Task tree section
                    Rectangle {
                        SplitView.fillHeight: workflowModel.selectedTaskId === ""
                        SplitView.minimumHeight: 100
                        SplitView.preferredHeight: 200
                        color: Theme.bgPanel

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingSmall
                            spacing: Theme.spacingSmall

                            // Tasks header
                            RowLayout {
                                Layout.fillWidth: true

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

                            // Task tree
                            ScrollView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true

                                TaskTree {
                                    id: taskTree
                                    width: parent.width
                                    tasks: workflowModel.selectedPhaseDetails.tasks || []
                                    selectedTask: workflowModel.selectedTask

                                    onTaskSelected: function(task) {
                                        if (task) {
                                            workflowModel.selectTask(task.id)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Task details section
                    Rectangle {
                        SplitView.minimumHeight: 32
                        SplitView.preferredHeight: workflowModel.selectedTaskId !== "" ? 300 : 32
                        color: Theme.bgPanel

                        // Empty state
                        Text {
                            anchors.centerIn: parent
                            text: "Select a task to view details"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textMuted
                            visible: workflowModel.selectedTaskId === ""
                        }

                        // Task details accordion
                        TaskDetailsAccordion {
                            anchors.fill: parent
                            visible: workflowModel.selectedTaskId !== ""
                            task: workflowModel.selectedTask
                        }
                    }
                }
            }
        }
    }
}
