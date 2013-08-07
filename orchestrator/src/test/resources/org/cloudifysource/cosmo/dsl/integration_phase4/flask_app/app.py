from flask import Flask, request
from os import path
import pickledb
import sys
app = Flask(__name__)


pickle_config_key_name = 'db_file'


def this_dir():
    return path.dirname(__file__)


@app.route("/")
def index():
    return "What are you doing here?"


@app.route("/admin", methods=['PUT'])
def admin():
    for key, value in request.form.items():
        print key, value
        with open(path.join(this_dir(), key), 'w') as f:
            f.write(value)
    return 'wrote request arguments'


def load_db():
    with open(path.join(this_dir(), pickle_config_key_name), 'rw') as f:
        db_path = f.read()
    return pickledb.load(db_path.strip(), False)


@app.route("/db/<key>")
def pickle_get(key):
    db = load_db()
    if not db:
        return 'No database is available'
    value = db.get(key)
    if not value:
        return '{0} not found in db'.format(key)
    return value


@app.route("/db/<key>/<value>", methods=['PUT'])
def pickle_put(key, value):
    db = load_db()
    previous = db.get(key)
    db.set(key, value)
    db.dump()
    return 'previous={0}'.format(previous)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
