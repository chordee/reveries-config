
import os
import tempfile
import hashlib
import codecs
import shutil
import weakref
import getpass

import pyblish.api
import avalon
from pyblish_qml.ipc import formatting


def temp_dir(prefix=""):
    """Provide a temporary directory
    This temporary directory is generated through `tempfile.mkdtemp()`
    """
    return tempfile.mkdtemp(prefix=prefix)


def clear_stage(prefix="tmp"):
    tempdir = tempfile.gettempdir()
    cwd_backup = os.getcwd()

    os.chdir(tempdir)
    for item in os.listdir(tempdir):
        if not (os.path.isdir(item) and item.startswith(prefix)):
            continue

        # Remove
        full_path = os.path.join(tempdir, item)
        print("Removing {!r}".format(full_path))
        shutil.rmtree(full_path)
        print("Removed.")

    os.chdir(cwd_backup)


def get_timeline_data():
    project = avalon.io.find_one({"type": "project"})
    asset = avalon.Session["AVALON_ASSET"]
    asset = avalon.io.find_one({"name": asset, "type": "asset"})

    def get_time(key):
        try:
            value = asset["data"][key]
        except KeyError:
            value = project["data"][key]
        return value

    edit_in = get_time("edit_in")
    edit_out = get_time("edit_out")
    handles = get_time("handles")
    fps = get_time("fps")

    if handles < 1:
        # (TODO) davidlatwe
        # Should not validate at here, need `project.data` schema to do that.
        raise ValueError("Incorrect value `Handles`: {}".format(handles))

    return edit_in, edit_out, handles, fps


def compose_timeline_data():
    edit_in, edit_out, handles, fps = get_timeline_data()
    start_frame = edit_in - handles
    end_frame = edit_out + handles

    return start_frame, end_frame, fps


def get_resolution_data():
    project = avalon.io.find_one({"type": "project"})
    resolution_width = project["data"].get("resolution_width", 1920)
    resolution_height = project["data"].get("resolution_height", 1080)
    return resolution_width, resolution_height


def init_app_workdir(*args):
    """Wrapped function of app initialize

    Copied from Colorbleed config, modified.
    Useful when changing task context, e.g. on_task_changed

    """

    # Inputs (from the switched session and running app)
    session = avalon.Session.copy()
    app_name = os.environ["AVALON_APP_NAME"]

    # Find the application definition
    app_definition = avalon.lib.get_application(app_name)

    App = type(
        "app_%s" % app_name,
        (avalon.api.Application,),
        {
            "name": app_name,
            "config": app_definition.copy()
        }
    )

    # Initialize within the new session's environment
    app = App()
    env = app.environ(session)
    app.initialize(env)


def override_event(event, callback):
    """Override existing event callback

    Copied from Colorbleed config.

    Args:
        event (str): name of the event
        callback (function): callback to be triggered

    Returns:
        None

    """

    ref = weakref.WeakSet()
    ref.add(callback)

    avalon.pipeline._registered_event_handlers[event] = ref


def publish_results_formatting(context):
    formatted = []
    for result in context.data["results"]:
        formatted.append(formatting.format_result(result))
    return formatted


def hash_file(file_path):
    hasher = AssetHasher()
    hasher.add_file(file_path)
    return hasher.digest()


def plugins_by_range(base=1.5, offset=2, paths=None):
    """Find plugins by thier order which fits in range

    Default param will return plugins that -0.5<=order<3.5, which is standard
    range of Pyblish CVEI.

    -.5 <= C < 0.5
    0.5 <= V < 1.5
    1.5 <= E < 2.5
    2.5 <= I < 3.5

    Arguments:
        base (float): Center of range
        offset (float, optional): Amount of offset from base

    """
    _min = base - offset
    _max = base + offset

    plugins = list()

    for plugin in pyblish.api.discover(paths=paths):
        if ("order" in plugin.__dict__ and
                _min <= plugin.order < _max):

            plugins.append(plugin)

    return plugins


class _C4Hasher(object):

    CHUNK_SIZE = 4096 * 10  # magic number
    PREFIX = "c4"

    def __init__(self):
        self.hash_obj = None
        self.clear()

    def clear(self):
        """Start a new hash session
        """
        self.hash_obj = hashlib.sha512()

    def _b58encode(self, bytes):
        """Base58 Encode bytes to string
        """
        b58chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        b58base = 58

        long_value = int(codecs.encode(bytes, "hex_codec"), 16)

        result = ""
        while long_value >= b58base:
            div, mod = divmod(long_value, b58base)
            result = b58chars[mod] + result
            long_value = div

        result = b58chars[long_value] + result

        return result

    def digest(self):
        """Return hash value of data added so far
        """
        c4_id_length = 90
        b58_hash = self._b58encode(self.hash_obj.digest())

        padding = ""
        if len(b58_hash) < (c4_id_length - 2):
            padding = "1" * (c4_id_length - 2 - len(b58_hash))

        c4id = self.PREFIX + padding + b58_hash
        return c4id


class AssetHasher(_C4Hasher):
    """A data hasher for digital content creation

    This is a Python implemtation of Avalanche-io C4 Asset ID.

    Usage:
        >> hasher = AssetHasher()
        >> hasher.add_file("/path/to/file")
        >> hasher.add_dir("/path/to/dir")

        You can keep adding more assets.
        And get the hash value by
        >> hasher.digest()
        'c463d2Wh5NyBMQRHyxbdBxCzZfaKXvBQaawgfgG18moxQU2jdmaSbCWL...'

        You can still adding more assets at this point
        >> hasher.add_file("/path/to/more/file")

        And get the hash value of all asset added so far
        >> hasher.digest()
        'c43cysVyTd7kYurvAa5ooR6miJJgUZ9QnBCHZeNK3en9aQ96KHsoJyJX...'

        Until you call `clear`
        >> hasher.clear()

    """

    def add_file(self, file_path):
        """Add one file to hasher

        Arguments:
            file_path (str): File path string

        """
        chunk_size = self.CHUNK_SIZE

        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(chunk_size), b""):
                self.hash_obj.update(chunk)

    def add_dir(self, dir_path, recursive=True, followlinks=True):
        """Add one directory to hasher

        Arguments:
            dir_path (str): Directory path string
            recursive (bool, optional): Add sub-dir as well, default is True
            followlinks (bool, optional): Add directories pointed to by
                symlinks, default is True

        """
        for root, dirs, files in os.walk(dir_path, followlinks=followlinks):
            for name in files:
                self.add_file(os.path.join(root, name))

            if not recursive:
                continue

            for name in dirs:
                path = os.path.join(root, name)
                self.add_dir(path, recursive=True, followlinks=followlinks)


def get_representation_path_(representation, parents):
    """Get filename from representation document

    Decoupled from `avalon.pipeline.get_representation_path`

    Args:
        representation (dict): representation document from the database
        parents (list): Documents returned from `io.parenthood`

    Returns:
        str: fullpath of the representation

    """
    version, subset, asset, project = parents
    template_publish = project["config"]["template"]["publish"]
    return template_publish.format(**{
        "root": avalon.api.registered_root(),
        "project": project["name"],
        "asset": asset["name"],
        "silo": asset["silo"],
        "subset": subset["name"],
        "version": version["name"],
        "representation": representation["name"],
        "user": avalon.api.Session.get("AVALON_USER", getpass.getuser()),
        "app": avalon.api.Session.get("AVALON_APP", ""),
        "task": avalon.api.Session.get("AVALON_TASK", "")
    })
