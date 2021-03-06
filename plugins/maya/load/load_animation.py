
import avalon.api
from reveries.maya.plugins import ReferenceLoader


class AnimationLoader(ReferenceLoader, avalon.api.Loader):
    """Specific loader of Alembic for the reveries.animation family"""

    label = "Reference Animation Edit"
    order = -10
    icon = "code-fork"
    color = "orange"

    hosts = ["maya"]

    families = ["reveries.animation"]

    representations = [
        "mayaAscii",
    ]

    def process_reference(self, context, name, namespace, options):
        # (TODO) load curves and other.
        pass

    def switch(self, container, representation):
        self.update(container, representation)
