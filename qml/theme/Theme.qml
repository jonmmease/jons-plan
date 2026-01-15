pragma Singleton
import QtQuick

/**
 * Centralized theme for the JonsPlan Workflow Viewer.
 * All colors, fonts, and spacing constants are defined here.
 */
QtObject {
    // Node status colors
    readonly property color nodeCurrentBg: "#e3f2fd"      // Light blue
    readonly property color nodeCurrentBorder: "#1976d2"  // Blue
    readonly property color nodeCompletedBg: "#e8f5e9"    // Light green
    readonly property color nodeCompletedBorder: "#4caf50" // Green
    readonly property color nodePendingBg: "#ffffff"      // White
    readonly property color nodePendingBorder: "#bdbdbd"  // Gray
    readonly property color nodeTerminalBg: "#fafafa"     // Very light gray
    readonly property color nodeTerminalBorder: "#9e9e9e" // Medium gray

    // Selection colors
    readonly property color selectionHighlight: "#ff9800" // Orange
    readonly property color hoverHighlight: "#90caf9"     // Light blue

    // Status indicator colors
    readonly property color statusCurrent: "#2196f3"      // Blue dot
    readonly property color statusCompleted: "#4caf50"    // Green dot
    readonly property color statusInProgress: "#ff9800"   // Orange dot
    readonly property color statusTodo: "#bdbdbd"         // Gray dot

    // Edge colors
    readonly property color edgeDefault: "#78909c"        // Blue-gray
    readonly property color edgeHover: "#546e7a"          // Darker blue-gray

    // Text colors
    readonly property color textPrimary: "#212121"        // Near black
    readonly property color textSecondary: "#757575"      // Medium gray
    readonly property color textMuted: "#9e9e9e"          // Light gray
    readonly property color textLink: "#1976d2"           // Blue

    // Background colors
    readonly property color bgWindow: "#fafafa"           // Very light gray
    readonly property color bgPanel: "#ffffff"            // White
    readonly property color bgPanelHeader: "#f5f5f5"      // Light gray
    readonly property color bgTimeline: "#eceff1"         // Blue-gray tint

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
    readonly property int nodeWidth: 120
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
    readonly property int treeIndent: 20              // Indentation per level
    readonly property color treeConnectorColor: textMuted  // Color for tree lines
    readonly property int taskNodeHeight: 28          // Height of each task row
    readonly property color taskSelectedBg: "#e3f2fd" // Selected task background
}
