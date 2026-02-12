from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QTimer, QPointF, QPropertyAnimation
from PySide6.QtGui import QColor
import sys
import math

from semantic_intelligence import build_semantic_tree
from pathlib import Path

NODE_RADIUS = 18
LEVEL_GAP = 120
SIBLING_GAP = 80


class TreeUI(QGraphicsView):
    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = root_dir
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.nodes = {}
        self.setRenderHint(self.renderHints() | self.renderHints())

        self.setWindowTitle("SEFS – Semantic File System")
        self.resize(1200, 800)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tree)
        self.timer.start(1000)  # UI refresh every 1s (cheap)

    def update_tree(self):
        tree = build_semantic_tree(self.root_dir)
        self.scene.clear()
        self.nodes.clear()
        self.draw_node(tree, 0, 0, 0)

    def draw_node(self, node, x, y, depth):
        color = {
            "root": QColor("#00FFD1"),
            "domain": QColor("#FFD700"),
            "cluster": QColor("#7EC8E3"),
            "file": QColor("#FFFFFF")
        }.get(node["type"], QColor("#AAAAAA"))

        circle = QGraphicsEllipseItem(
            -NODE_RADIUS, -NODE_RADIUS,
            NODE_RADIUS * 2, NODE_RADIUS * 2
        )
        circle.setBrush(color)
        circle.setPos(x, y)
        self.scene.addItem(circle)

        label = QGraphicsTextItem(node["name"])
        label.setDefaultTextColor(Qt.white)
        label.setPos(x - NODE_RADIUS, y + NODE_RADIUS)
        self.scene.addItem(label)

        children = node.get("children", [])
        width = (len(children) - 1) * SIBLING_GAP
        start_x = x - width / 2

        for i, child in enumerate(children):
            cx = start_x + i * SIBLING_GAP
            cy = y + LEVEL_GAP
            self.draw_node(child, cx, cy, depth + 1)


def run_ui(root_dir):
    app = QApplication(sys.argv)
    ui = TreeUI(root_dir)
    ui.show()
    sys.exit(app.exec())
