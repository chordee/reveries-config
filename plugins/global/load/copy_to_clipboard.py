
import avalon.api
from reveries.plugins import PackageLoader


class CopyToClipboardLoader(PackageLoader, avalon.api.Loader):
    """Copy published file to clipboard to allow to paste the content"""
    representations = ["*"]
    families = ["*"]

    label = "Copy Path"
    order = 20
    icon = "clipboard"
    color = "#999999"

    def load(self, context, name=None, namespace=None, data=None):
        self.log.info("Added to clipboard: {0}".format(self.package_path))
        self.copy_path_to_clipboard(self.package_path)

    @staticmethod
    def copy_path_to_clipboard(path):
        from avalon.vendor.Qt import QtCore, QtWidgets

        app = QtWidgets.QApplication.instance()
        assert app, "Must have running QApplication instance"

        # Build mime data for clipboard
        mime = QtCore.QMimeData()
        mime.setText(path)
        mime.setUrls([QtCore.QUrl.fromLocalFile(path)])

        # Set to Clipboard
        clipboard = app.clipboard()
        clipboard.setMimeData(mime)
