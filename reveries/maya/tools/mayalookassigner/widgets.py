import logging

from avalon.vendor.Qt import QtWidgets, QtCore

# TODO: expose this better in avalon core
from avalon.tools.projectmanager.widget import (
    preserve_selection,
    preserve_expanded_rows
)

from . import models
from . import commands
from . import views


NODEROLE = QtCore.Qt.UserRole + 1
MODELINDEX = QtCore.QModelIndex()


class AssetOutliner(QtWidgets.QWidget):

    refreshed = QtCore.Signal()
    selection_changed = QtCore.Signal()

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("Assets")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")

        model = models.AssetModel()
        view = views.View()
        view.setModel(model)
        view.customContextMenuRequested.connect(self.right_mouse_menu)
        view.setSortingEnabled(False)
        view.setHeaderHidden(True)
        view.setIndentation(10)

        from_all_asset_btn = QtWidgets.QPushButton("Get All Assets")
        from_selection_btn = QtWidgets.QPushButton("Get Assets From Selection")

        layout.addWidget(title)
        layout.addWidget(from_all_asset_btn)
        layout.addWidget(from_selection_btn)
        layout.addWidget(view)

        # Build connections
        from_selection_btn.clicked.connect(self.get_selected_assets)
        from_all_asset_btn.clicked.connect(self.get_all_assets)

        selection_model = view.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)

        self.view = view
        self.model = model

        self.setLayout(layout)

        self.log = logging.getLogger(__name__)

    def clear(self):
        self.model.clear()

        # fix looks remaining visible when no items present after "refresh"
        # todo: figure out why this workaround is needed.
        self.selection_changed.emit()

    def add_items(self, items):
        """Add new items to the outliner"""

        self.model.add_items(items)
        self.refreshed.emit()

    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        selection_model = self.view.selectionModel()
        items = [row.data(NODEROLE) for row in
                 selection_model.selectedRows(0)]

        return items

    def get_all_assets(self):
        """Add all items from the current scene"""

        with preserve_expanded_rows(self.view):
            with preserve_selection(self.view):
                self.clear()
                nodes = commands.get_all_asset_nodes()
                items = commands.create_items_from_nodes(nodes)
                self.add_items(items)

        return len(items) > 0

    def get_selected_assets(self):
        """Add all selected items from the current scene"""

        with preserve_expanded_rows(self.view):
            with preserve_selection(self.view):
                self.clear()
                nodes = commands.get_selected_nodes()
                items = commands.create_items_from_nodes(nodes)
                self.add_items(items)

    def get_nodes(self):
        """Find the nodes in the current scene per asset."""

        items = self.get_selected_items()

        # Collect the asset item entries per asset
        assets = dict()
        for item in items:
            asset_name = item["asset"]["name"]

            namespaces = item.get("namespace", item["namespaces"])
            nodes = commands.get_interface_from_namespace(namespaces)

            assets[asset_name] = item
            assets[asset_name]["nodes"] = nodes

        return assets

    def select_asset_from_items(self):
        """Select nodes from listed asset"""

        items = self.get_nodes()
        nodes = []
        for item in items.values():
            nodes.extend(item["nodes"])

        commands.select(nodes)

    def right_mouse_menu(self, pos):
        """Build RMB menu for asset outliner"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Select nodes")
        apply_action.triggered.connect(self.select_asset_from_items)

        if not active.isValid():
            apply_action.setEnabled(False)

        menu.addAction(apply_action)

        menu.exec_(globalpos)


class LookOutliner(QtWidgets.QWidget):

    menu_apply_action = QtCore.Signal()

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        # look manager layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Looks from database
        title = QtWidgets.QLabel("Looks")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")
        title.setAlignment(QtCore.Qt.AlignCenter)

        model = models.LookModel()

        # Proxy for dynamic sorting
        proxy = QtCore.QSortFilterProxyModel()
        proxy.setSourceModel(model)

        view = views.View()
        view.setModel(proxy)
        view.setMinimumHeight(180)
        view.setToolTip("Use right mouse button menu for direct actions")
        view.customContextMenuRequested.connect(self.right_mouse_menu)
        view.sortByColumn(0, QtCore.Qt.AscendingOrder)

        layout.addWidget(title)
        layout.addWidget(view)

        self.view = view
        self.model = model

    def clear(self):
        self.model.clear()

    def add_items(self, items):
        self.model.add_items(items)

    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        datas = [i.data(NODEROLE) for i in self.view.get_indices()]
        items = [d for d in datas if d is not None]  # filter Nones

        return items

    def right_mouse_menu(self, pos):
        """Build RMB menu for look view"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        if not active.isValid():
            return

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Assign looks..")
        apply_action.triggered.connect(self.menu_apply_action)

        menu.addAction(apply_action)

        menu.exec_(globalpos)
