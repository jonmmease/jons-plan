pragma Singleton
import QtQuick

/**
 * Centralized theme for the JonsPlan Workflow Viewer.
 * Supports light and dark modes based on workflowModel.isDark.
 */
QtObject {
    // Dark mode state - bound to workflowModel in main.qml
    property bool isDark: false

    // Node status colors
    property color nodeCurrentBg: isDark ? "#1e3a5f" : "#e3f2fd"
    property color nodeCurrentBorder: isDark ? "#4fc3f7" : "#1976d2"
    property color nodeCompletedBg: isDark ? "#1e3a2f" : "#e8f5e9"
    property color nodeCompletedBorder: isDark ? "#81c784" : "#4caf50"
    property color nodePendingBg: isDark ? "#2d2d30" : "#ffffff"
    property color nodePendingBorder: isDark ? "#5a5a5a" : "#bdbdbd"
    property color nodeTerminalBg: isDark ? "#252526" : "#fafafa"
    property color nodeTerminalBorder: isDark ? "#6e6e6e" : "#9e9e9e"

    // Selection colors
    property color selectionHighlight: "#ff9800"  // Orange - same in both
    property color hoverHighlight: isDark ? "#3a4a5a" : "#90caf9"

    // Status indicator colors (same in both modes for consistency)
    readonly property color statusCurrent: "#2196f3"
    readonly property color statusCompleted: "#4caf50"
    readonly property color statusInProgress: "#ff9800"
    readonly property color statusTodo: isDark ? "#6e6e6e" : "#bdbdbd"

    // Edge colors
    property color edgeDefault: isDark ? "#6e7681" : "#78909c"
    property color edgeHover: isDark ? "#8b949e" : "#546e7a"
    property color edgeBlocked: isDark ? "#b33a3a" : "#8b0000"  // Dark red/crimson for blocked transitions

    // Text colors
    property color textPrimary: isDark ? "#d4d4d4" : "#212121"
    property color textSecondary: isDark ? "#9e9e9e" : "#757575"
    property color textMuted: isDark ? "#6e6e6e" : "#9e9e9e"
    property color textLink: isDark ? "#3794ff" : "#1976d2"

    // Background colors
    property color bgWindow: isDark ? "#1e1e1e" : "#fafafa"
    property color bgPanel: isDark ? "#252526" : "#ffffff"
    property color bgPanelHeader: isDark ? "#2d2d30" : "#f5f5f5"
    property color bgTimeline: isDark ? "#1e1e1e" : "#eceff1"

    // Border colors (for separators)
    property color borderLight: isDark ? "#3e3e42" : "#e0e0e0"

    // Font sizes
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeMedium: 14
    readonly property int fontSizeLarge: 16
    readonly property int fontSizeTitle: 18
    readonly property int fontSizeHeader: 20

    // Spacing
    readonly property int spacingTiny: 4
    readonly property int spacingSmall: 8
    readonly property int spacingMedium: 12
    readonly property int spacingLarge: 16
    readonly property int spacingXLarge: 24

    // Border radius
    readonly property int radiusSmall: 4
    readonly property int radiusNormal: 8
    readonly property int radiusLarge: 12

    // Node dimensions
    readonly property int nodeWidth: 180
    readonly property int nodeHeight: 50
    readonly property int nodeRadius: 8

    // Edge styling
    readonly property int edgeWidth: 2

    // Animation durations (ms)
    readonly property int animFast: 100
    readonly property int animNormal: 200
    readonly property int animSlow: 300

    // Panel dimensions
    readonly property int detailsPanelWidth: 300
    readonly property int timelinePanelHeight: 150

    // Task tree styling
    readonly property int treeIndent: 20
    property color treeConnectorColor: textMuted
    readonly property int taskNodeHeight: 28
    property color taskSelectedBg: isDark ? "#1e3a5f" : "#e3f2fd"

    // Helper to wrap HTML content with text color for RichText display
    function wrapHtml(content, color) {
        var c = color || textPrimary
        // Convert QML color to CSS hex format
        var hex = "#" + Math.round(c.r * 255).toString(16).padStart(2, '0') +
                        Math.round(c.g * 255).toString(16).padStart(2, '0') +
                        Math.round(c.b * 255).toString(16).padStart(2, '0')
        return "<div style='color: " + hex + ";'>" + (content || "") + "</div>"
    }
}
