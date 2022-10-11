import base64
import hashlib
import json
import os


class Definitions:
    def __init__(self):
        self.file_path = "/etc/cloudify/rabbitmq/definitions.json"

    def configure(self):
        username = self._get_username()
        password = self._get_password()
        password_hash = self._get_password_hash(password)

        definitions = self._read_definitions()

        definitions["users"][0]["name"] = username
        definitions["users"][0]["password_hash"] = password_hash

        definitions["permissions"][0]["user"] = username

        self._write_definitions(definitions)

    def _read_definitions(self):
        with open(self.file_path, 'r') as file:
            return json.load(file)

    def _write_definitions(self, definitions):
        with open(self.file_path, 'w') as file:
            json.dump(definitions, file, indent=4)

    @staticmethod
    def _get_username():
        return os.environ['RABBITMQ_USERNAME']

    @staticmethod
    def _get_password():
        return os.environ['RABBITMQ_PASSWORD']

    @staticmethod
    def _get_password_hash(password):
        salt = os.urandom(4)
        hashed = hashlib.sha256(salt + password.encode('utf-8')).digest()

        return base64.b64encode(salt + hashed).decode('utf-8')


def main():
    definitions = Definitions()
    definitions.configure()


if __name__ == "__main__":
    main()
