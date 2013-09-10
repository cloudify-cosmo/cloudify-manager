import os
import tempfile

__author__ = 'elip'
import unittest
from plugin_installer.tasks import get_plugin_simple_name, create_namespace_path, install_celery_plugin_to_dir
from plugin_installer.tests import get_logger

logger = get_logger("PluginInstallerTestCase")


class PluginInstallerTestCase(unittest.TestCase):

    def test_install(self):
        name = "a.b.c"
        assert get_plugin_simple_name(name) == "c"

    def test_create_namespace_path(self):

        base_dir = tempfile.NamedTemporaryFile().name

        namespace_parts = ["cloudify", "tosca", "artifacts", "plugin"]
        create_namespace_path(namespace_parts, base_dir)

        # lets make sure the correct structure was created
        namespace_path = base_dir
        for folder in namespace_parts:
            namespace_path = os.path.join(namespace_path, folder)
            with open(os.path.join(namespace_path,  "__init__.py")) as f:
                init_data = f.read()
                # we create empty init files
                assert init_data == ""

    def test_install(self):

        name = "test.plugin.mock"
        package_name = "mock-plugin"
        url = os.path.join(os.path.dirname(__file__), "mock-plugin")

        base_dir = tempfile.NamedTemporaryFile().name

        install_celery_plugin_to_dir(url,
                                     name,
                                     package_name,
                                     base_dir)

        expected_plugin_path = os.path.join(base_dir, name.replace(".", "/"))

        assert os.path.exists(expected_plugin_path)

