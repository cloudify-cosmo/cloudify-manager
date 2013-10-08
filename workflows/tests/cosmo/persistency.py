__author__ = 'dan'

import os
import json
from os import path


class Persist:

    def __init__(self, name):
        self.name = name

    def _get_data_file_path(self):
        return path.join(os.environ["TEMP_DIR"], self.name)

    def read(self):
        data_file_path = self._get_data_file_path()
        if not path.exists(data_file_path):
            return dict()
        with open(data_file_path, "r") as f:
            return json.loads(f.read())

    def write(self, data):
        data_file_path = self._get_data_file_path()
        if path.exists(data_file_path):
            os.remove(data_file_path)
        with open(data_file_path, "w") as f:
            f.write(json.dumps(data))