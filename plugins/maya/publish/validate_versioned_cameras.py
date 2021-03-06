
import pyblish.api
from avalon.pipeline import AVALON_CONTAINER_ID
from reveries.maya.plugins import MayaSelectInvalidAction


class SelectInvalid(MayaSelectInvalidAction):

    label = "Select Invalid Cameras"


class ValidateVersionedCameras(pyblish.api.InstancePlugin):
    """Camera must be containerized
    """

    order = pyblish.api.ValidatorOrder
    hosts = ["maya"]
    label = "Has Versioned Camera"
    families = [
        "reveries.imgseq",
    ]

    actions = [
        pyblish.api.Category("Select"),
        SelectInvalid,
    ]

    @classmethod
    def get_invalid(cls, instance):
        from reveries.maya import lib
        from maya import cmds

        containers = lib.lsAttr("id", AVALON_CONTAINER_ID)

        has_versioned = set()
        cameras = set(instance.data["renderCam"])

        for cam in cameras:
            transform = cmds.listRelatives(cam, parent=True, fullPath=True)[0]
            for set_ in cmds.listSets(object=transform) or []:
                if set_ in containers:
                    has_versioned.add(cam)

        return list(cameras - has_versioned)

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise Exception("Camera not versioned.")
