
import os
from maya import cmds
from collections import OrderedDict

import pyblish.api
import avalon.maya
from reveries.plugins import context_process
from reveries.maya import lib, utils


def publish_on_lock(instance):
    """Block instance if scene is not locked"""
    if not avalon.maya.is_locked():
        instance.data["optional"] = False
        instance.data["publish"] = False


def set_extraction_type(instance):
    if len(instance.data["outputPaths"]) > 1:
        instance.data["extractType"] = "imageSequenceSet"
    else:
        instance.data["extractType"] = "imageSequence"


class CollectRenderlayers(pyblish.api.InstancePlugin):
    """Gather instances by active render layers
    """

    order = pyblish.api.CollectorOrder - 0.299
    hosts = ["maya"]
    label = "Avalon Instances (Render)"
    families = ["reveries.imgseq"]

    def get_render_attr(self, attr, layer):
        return lib.query_by_renderlayer("defaultRenderGlobals",
                                        attr,
                                        layer)

    def get_pipeline_attr(self, layer):
        pipeline_attrs = [
            "asset",
            "subset",
            "renderType",
            "deadlineEnable",
            "deadlinePool",
            "deadlineGroup",
            "deadlinePriority",
        ]
        return {k: lib.query_by_renderlayer(self.instance_node,
                                            k,
                                            layer)
                for k in pipeline_attrs}

    @context_process
    def process(self, context):

        self.instance_node = None
        dummy_members = list()

        # Remove all dummy `imgseq` instances
        for instance in list(context):
            if instance.data["family"] in self.families:
                self.instance_node = instance.data.get("objectName")
                dummy_members = instance[:]
                context.remove(instance)

        assert self.instance_node is not None, "This is a bug."

        # Get all valid renderlayers
        # This is how Maya populates the renderlayer display
        rlm_attribute = "renderLayerManager.renderLayerId"
        connected_layers = cmds.listConnections(rlm_attribute) or []
        valid_layers = set(connected_layers)

        # Context data

        workspace = context.data["workspaceDir"]
        context.data["outputDir"] = os.path.join(workspace, "renders")

        context.data["_has_privileged_instance"] = True
        # Are there other renderlayer than defaultRenderLayer ?
        context.data["hasRenderLayers"] = len(valid_layers) > 1
        # Using Render Setup system ?
        if context.data["mayaVersion"] >= 2016.5:
            context.data["usingRenderSetup"] = cmds.mayaHasRenderSetup()
        else:
            context.data["usingRenderSetup"] = False

        # Create instance by renderlayers

        # Get all renderlayers and check their state
        renderlayers = [i for i in cmds.ls(type="renderLayer") if
                        cmds.getAttr("{}.renderable".format(i)) and not
                        cmds.referenceQuery(i, isNodeReferenced=True)]
        # By renderlayer displayOrder
        for layer in sorted(renderlayers,
                            key=lambda l: cmds.getAttr("%s.displayOrder" % l)):

            self.log.debug("Creating instance for renderlayer: %s" % layer)

            # Check if layer is in valid (linked) layers
            if layer not in valid_layers:
                self.log.warning("%s is invalid, skipping" % layer)
                continue

            if layer.endswith("defaultRenderLayer"):
                layername = "masterLayer"
            else:
                layername = layer

            renderer = self.get_render_attr("currentRenderer", layer)
            name_preview = utils.compose_render_filename(layer)
            ext = os.path.splitext(name_preview)[-1]

            # Get layer specific settings, might be overrides
            data = {
                "renderlayer": layer,
                "startFrame": self.get_render_attr("startFrame", layer),
                "endFrame": self.get_render_attr("endFrame", layer),
                "byFrameStep": self.get_render_attr("byFrameStep", layer),
                "renderer": renderer,
                "fileNamePrefix": utils.get_render_filename_prefix(layer),
                "fileExt": ext,
            }

            data.update(self.get_pipeline_attr(layer))

            instance = context.create_instance(layername)
            instance[:] = dummy_members
            instance.data.update(data)

            # For dependency tracking
            instance.data["dependencies"] = dict()
            instance.data["futureDependencies"] = dict()

            # By default, image sequence can be published no matter scene is
            # locked or not.
            instance.data["_privilege_on_lock"] = True

            instance.data["family"] = "reveries.imgseq"
            instance.data["families"] = list()
            variate = getattr(self, "process_" + instance.data["renderType"])
            variate(instance, layer)

            # Collect renderlayer members

            members = cmds.editRenderLayerMembers(layer, query=True) or []

            instance.data["renderLayerMember"] = cmds.ls(members, long=True)
            descendent = cmds.listRelatives(members, allDescendents=True) or []
            members += descendent

            # Collect all meshes, for building dependency connections
            # (TODO) Append only mesh type objects to build dependency
            # connections is for avoiding potential non-acyclic dependency
            # relationships.
            meshes = cmds.ls(members,
                             type="mesh", noIntermediate=True, long=True)
            transforms = cmds.listRelatives(meshes,
                                            parent=True, fullPath=True) or []
            instance += transforms

    def collect_output_paths(self, instance):
        renderer = instance.data["renderer"]
        layer = instance.data["renderlayer"]

        paths = OrderedDict()

        if renderer == "vray":
            import reveries.maya.vray.utils as utils_
            aov_names = utils_.get_vray_element_names(layer)

        elif renderer == "arnold":
            import reveries.maya.arnold.utils as utils_
            aov_names = utils_.get_arnold_aov_names(layer)

        else:
            aov_names = []

        aov_names.append("")

        output_dir = instance.context.data["outputDir"]

        for aov in aov_names:
            output_prefix = utils.compose_render_filename(layer, aov)
            output_path = output_dir + "/" + output_prefix

            paths[aov] = output_path.replace("\\", "/")

            self.log.debug("Collecting AOV output path: %s" % aov)
            self.log.debug("                      path: %s" % paths[aov])

        instance.data["outputPaths"] = paths

    def process_playblast(self, instance, layer):
        """
        """
        # Inject shadow family
        instance.data["families"] = ["reveries.imgseq.playblast"]
        instance.data["category"] = "Playblast"
        publish_on_lock(instance)

        # Assign contractor
        if instance.data["deadlineEnable"]:
            instance.data["useContractor"] = True
            instance.data["publishContractor"] = "deadline.maya.script"

        # Collect cameras
        hierarchy = instance[:]
        hierarchy += cmds.listRelatives(instance, allDescendents=True)
        instance.data["renderCam"] = cmds.ls(hierarchy,
                                             type="camera",
                                             long=True)

    def process_turntable(self, instance, layer):
        """
        """
        # Update subset name with layername
        instance.data["subset"] += "." + instance.name

        # Inject shadow family
        instance.data["families"] = ["reveries.imgseq.turntable"]
        instance.data["category"] = "Turntable: " + instance.data["renderer"]
        publish_on_lock(instance)

        # Assign contractor
        if instance.data["deadlineEnable"]:
            instance.data["useContractor"] = True
            instance.data["publishContractor"] = "deadline.maya.render"

        # Collect renderable cameras
        hierarchy = instance[:]
        hierarchy += cmds.listRelatives(instance, allDescendents=True)
        instance_cam = set(cmds.ls(hierarchy, type="camera", long=True))
        renderable_cam = set(lib.ls_renderable_cameras(layer))
        render_cam = list(instance_cam.intersection(renderable_cam))
        instance.data["renderCam"] = render_cam

        self.collect_output_paths(instance)
        set_extraction_type(instance)

    def process_batchrender(self, instance, layer):
        """
        """
        # Update subset name with layername
        instance.data["subset"] += "." + instance.name

        # Inject shadow family
        instance.data["families"] = ["reveries.imgseq.batchrender"]
        instance.data["category"] = "Render: " + instance.data["renderer"]

        # Assign contractor
        if instance.data["deadlineEnable"]:
            instance.data["useContractor"] = True
            instance.data["publishContractor"] = "deadline.maya.render"

        # Collect renderable cameras
        hierarchy = instance[:]
        hierarchy += cmds.listRelatives(instance, allDescendents=True)
        instance_cam = set(cmds.ls(hierarchy, type="camera", long=True))
        renderable_cam = set(lib.ls_renderable_cameras(layer))
        render_cam = list(instance_cam.intersection(renderable_cam))
        instance.data["renderCam"] = render_cam

        self.collect_output_paths(instance)
        set_extraction_type(instance)
