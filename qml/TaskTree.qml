import QtQuick
import QtQuick.Layouts
import "theme"

/**
 * TaskTree - Displays tasks as a dependency tree.
 * Terminal tasks (no dependents) appear at root, dependencies nested below.
 * DAG handling: repeated tasks show ↗ marker and don't expand.
 */
Item {
    id: root

    property var tasks: []           // Input: array of task objects
    property var selectedTask: null  // Currently selected task

    signal taskSelected(var task)

    // Computed tree model
    property var treeModel: buildTreeModel(tasks)

    implicitHeight: treeColumn.implicitHeight

    // Build tree structure from flat task array
    function buildTreeModel(taskList) {
        if (!taskList || taskList.length === 0) return []

        // Build maps
        let taskMap = {}
        let childrenOf = {}

        for (let task of taskList) {
            taskMap[task.id] = task
            childrenOf[task.id] = []
        }

        // Build reverse map (children of each task)
        for (let task of taskList) {
            if (task.parents) {
                for (let parentId of task.parents) {
                    if (childrenOf[parentId]) {
                        childrenOf[parentId].push(task.id)
                    }
                }
            }
        }

        // Find terminal tasks (no children = no dependents)
        let terminals = taskList.filter(t => childrenOf[t.id].length === 0)

        // Build tree from terminals
        let seen = {}
        return terminals.map(t => buildNode(t.id, taskMap, seen))
    }

    // Recursively build tree node
    function buildNode(taskId, taskMap, seen) {
        let isRepeat = seen[taskId] === true
        seen[taskId] = true

        let task = taskMap[taskId]
        if (!task) return null

        let children = []
        if (!isRepeat && task.parents) {
            for (let parentId of task.parents) {
                let childNode = buildNode(parentId, taskMap, seen)
                if (childNode) children.push(childNode)
            }
        }

        return {
            task: task,
            isRepeat: isRepeat,
            children: children
        }
    }

    // Tree content
    Column {
        id: treeColumn
        width: parent.width
        spacing: 0

        // Empty state
        Text {
            visible: root.treeModel.length === 0
            text: "No tasks in this phase"
            font.pixelSize: Theme.fontSizeNormal
            color: Theme.textMuted
            leftPadding: Theme.spacingSmall
        }

        // Tree nodes
        Repeater {
            model: root.treeModel

            TreeNode {
                width: treeColumn.width
                task: modelData.task
                depth: 0
                isRepeat: modelData.isRepeat
                children: modelData.children
                isSelected: Boolean(root.selectedTask && modelData.task &&
                           root.selectedTask.id === modelData.task.id)

                onTaskClicked: function(clickedTask) {
                    root.selectedTask = clickedTask
                    root.taskSelected(clickedTask)
                }
            }
        }
    }
}
