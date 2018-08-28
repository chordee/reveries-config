
import os
import json
import logging
from maya import cmds

from . import capsule
from .vendor import capture


log = logging.getLogger(__name__)


def export_fbx(out_path, selected=True):
    from pymel.core import mel as pymel
    try:
        pymel.FBXExport(f=out_path, s=selected)
    finally:
        pymel.FBXResetExport()


def export_fbx_set_pointcache(cache_set_name):
    cmds.sets(cmds.ls(sl=True), name=cache_set_name)
    fbx_export_settings(reset=True,
                        log=False,
                        ascii=True,
                        cameras=False,
                        lights=False,
                        cache_file=True,
                        cache_set=cache_set_name,
                        anim_only=False,
                        key_reduce=True,
                        shapes=False,
                        skins=False,
                        input_conns=False,
                        )


def export_fbx_set_camera():
    fbx_export_settings(reset=True,
                        log=False,
                        ascii=True,
                        cameras=True,
                        lights=False,
                        )


def fbx_export_settings(reset=False, **kwargs):
    """
    """
    from pymel.core import mel as pymel

    if reset:
        pymel.FBXResetExport()

    fbx_export_cmd_map = {
        "log": pymel.FBXExportGenerateLog,
        "ascii": pymel.FBXExportInAscii,
        "version": pymel.FBXExportFileVersion,

        "cameras": pymel.FBXExportCameras,
        "lights": pymel.FBXExportLights,
        "instances": pymel.FBXExportInstances,
        "referenced": pymel.FBXExportReferencedAssetsContent,

        "smoothing_groups": pymel.FBXExportSmoothingGroups,
        "smooth_mesh": pymel.FBXExportSmoothMesh,
        "tangents": pymel.FBXExportTangents,
        "triangulate": pymel.FBXExportTriangulate,
        "hardEdges": pymel.FBXExportHardEdges,

        "constraints": pymel.FBXExportConstraints,
        "input_conns": pymel.FBXExportInputConnections,

        "shapes": pymel.FBXExportShapes,
        "skins": pymel.FBXExportSkins,
        "skeleton": pymel.FBXExportSkeletonDefinitions,

        "anim_only": pymel.FBXExportAnimationOnly,
        "cache_file": pymel.FBXExportCacheFile,
        "cache_set": pymel.FBXExportQuickSelectSetAsCache,

        "bake_anim": pymel.FBXExportBakeComplexAnimation,
        "bake_start": pymel.FBXExportBakeComplexStart,
        "bake_end": pymel.FBXExportBakeComplexEnd,
        "bake_step": pymel.FBXExportBakeComplexStep,
        "bake_resample_all": pymel.FBXExportBakeResampleAll,

        "key_reduce": pymel.FBXExportApplyConstantKeyReducer,
    }

    for key in kwargs:
        fbx_export_cmd_map[key](v=kwargs[key])


# The maya alembic export types
_alembic_options = {
    "startFrame": (int, float),
    "endFrame": (int, float),
    "frameRange": str,  # "start end"; overrides startFrame & endFrame
    "eulerFilter": bool,
    "frameRelativeSample": float,
    "noNormals": bool,
    "renderableOnly": bool,
    "step": float,
    "stripNamespaces": bool,
    "uvWrite": bool,
    "wholeFrameGeo": bool,
    "worldSpace": bool,
    "writeVisibility": bool,
    "writeColorSets": bool,
    "writeFaceSets": bool,
    "writeCreases": bool,  # Maya 2015 Ext1+
    "dataFormat": str,
    "root": (list, tuple),
    "attr": (list, tuple),
    "attrPrefix": (list, tuple),
    "userAttr": (list, tuple),
    "melPerFrameCallback": str,
    "melPostJobCallback": str,
    "pythonPerFrameCallback": str,
    "pythonPostJobCallback": str,
    "selection": bool
}


def export_alembic(file,
                   startFrame=None,
                   endFrame=None,
                   selected=True,
                   uvWrite=True,
                   eulerFilter=True,
                   writeVisibility=True,
                   dataFormat="ogawa",
                   verbose=False,
                   **kwargs):
    """Extract a single Alembic Cache. (modified, from colorbleed config)

    Arguments:

        startFrame (float): Start frame of output. Ignored if `frameRange`
            provided.

        endFrame (float): End frame of output. Ignored if `frameRange`
            provided.

        frameRange (tuple or str): Two-tuple with start and end frame or a
            string formatted as: "startFrame endFrame". This argument
            overrides `startFrame` and `endFrame` arguments.

        dataFormat (str): The data format to use for the cache,
                          defaults to "ogawa"

        verbose (bool): When on, outputs frame number information to the
            Script Editor or output window during extraction.

        noNormals (bool): When on, normal data from the original polygon
            objects is not included in the exported Alembic cache file.

        renderableOnly (bool): When on, any non-renderable nodes or hierarchy,
            such as hidden objects, are not included in the Alembic file.
            Defaults to False.

        stripNamespaces (bool): When on, any namespaces associated with the
            exported objects are removed from the Alembic file. For example, an
            object with the namespace taco:foo:bar appears as bar in the
            Alembic file.

        uvWrite (bool): When on, UV data from polygon meshes and subdivision
            objects are written to the Alembic file. Only the current UV map is
            included.

        worldSpace (bool): When on, the top node in the node hierarchy is
            stored as world space. By default, these nodes are stored as local
            space. Defaults to False.

        eulerFilter (bool): When on, X, Y, and Z rotation data is filtered with
            an Euler filter. Euler filtering helps resolve irregularities in
            rotations especially if X, Y, and Z rotations exceed 360 degrees.
            Defaults to True.

        writeVisibility (bool): If this flag is present, visibility state will
            be stored in the Alembic file.
            Otherwise everything written out is treated as visible.

    """

    # Ensure alembic exporter is loaded
    cmds.loadPlugin('AbcExport', quiet=True)

    # Alembic Exporter requires forward slashes
    file = file.replace('\\', '/')

    # Pass the start and end frame on as `frameRange` so that it
    # never conflicts with that argument
    if "frameRange" not in kwargs:
        # Fallback to maya timeline if no start or end frame provided.
        if startFrame is None:
            startFrame = cmds.playbackOptions(query=True, minTime=True)
        if endFrame is None:
            endFrame = cmds.playbackOptions(query=True, maxTime=True)

        # Ensure valid types are converted to frame range
        assert isinstance(startFrame, _alembic_options["startFrame"])
        assert isinstance(endFrame, _alembic_options["endFrame"])
        kwargs["frameRange"] = "{0} {1}".format(startFrame, endFrame)
    else:
        # Allow conversion from tuple for `frameRange`
        frame_range = kwargs["frameRange"]
        if isinstance(frame_range, (list, tuple)):
            assert len(frame_range) == 2
            kwargs["frameRange"] = "{0} {1}".format(frame_range[0],
                                                    frame_range[1])

    # Assemble options
    options = {
        "selection": selected,
        "uvWrite": uvWrite,
        "eulerFilter": eulerFilter,
        "writeVisibility": writeVisibility,
        "dataFormat": dataFormat
    }
    options.update(kwargs)

    # Validate options
    for key, value in options.copy().items():

        # Discard unknown options
        if key not in _alembic_options:
            options.pop(key)
            continue

        # Validate value type
        valid_types = _alembic_options[key]
        if not isinstance(value, valid_types):
            raise TypeError("Alembic option unsupported type: "
                            "{0} (expected {1})".format(value, valid_types))

    # The `writeCreases` argument was changed to `autoSubd` in Maya 2018+
    maya_version = int(cmds.about(version=True))
    if maya_version >= 2018:
        options['autoSubd'] = options.pop('writeCreases', False)

    # Format the job string from options
    job_args = list()
    for key, value in options.items():
        if isinstance(value, (list, tuple)):
            for entry in value:
                job_args.append("-{} {}".format(key, entry))
        elif isinstance(value, bool):
            # Add only when state is set to True
            if value:
                job_args.append("-{0}".format(key))
        else:
            job_args.append("-{0} {1}".format(key, value))

    job_str = " ".join(job_args)
    job_str += ' -file "%s"' % file

    # Ensure output directory exists
    parent_dir = os.path.dirname(file)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    if verbose:
        log.debug("Preparing Alembic export with options: %s",
                  json.dumps(options, indent=4))
        log.debug("Extracting Alembic with job arguments: %s", job_str)

    # Perform extraction
    print("Alembic Job Arguments : {}".format(job_str))

    # Disable the parallel evaluation temporarily to ensure no buggy
    # exports are made. (PLN-31)
    # TODO: Make sure this actually fixes the issues
    with capsule.evaluation("off"):
        cmds.AbcExport(j=job_str, verbose=verbose)

    if verbose:
        log.debug("Extracted Alembic to: %s", file)

    return file


def export_gpu(out_path, startFrame, endFrame):
    cmds.gpuCache(cmds.ls(sl=True, long=True),
                  startTime=startFrame,
                  endTime=endFrame,
                  optimize=True,
                  optimizationThreshold=40000,
                  writeMaterials=True,
                  writeUVs=True,
                  dataFormat="ogawa",
                  saveMultipleFiles=False,
                  directory=os.path.dirname(out_path),
                  fileName=os.path.splitext(os.path.basename(out_path))[0]
                  )


def capture_seq(camera,
                filename,
                start_frame,
                end_frame,
                width=None,
                height=None,
                isolate=None,
                frame_padding=4,
                display_options=None,
                viewport_options=None):

    viewport_options = viewport_options or {
        "headsUpDisplay": False,
    }

    output = capture.capture(
        camera,
        filename=filename,
        start_frame=start_frame,
        end_frame=end_frame,
        width=width,
        height=height,
        format='image',
        compression='png',
        quality=100,
        off_screen=True,
        viewer=False,
        show_ornaments=False,
        sound=None,
        isolate=isolate,
        maintain_aspect_ratio=True,
        overwrite=True,
        frame_padding=frame_padding,
        raw_frame_numbers=False,
        camera_options=None,
        display_options=display_options,
        viewport_options=viewport_options,
        viewport2_options=None
    )
    return output