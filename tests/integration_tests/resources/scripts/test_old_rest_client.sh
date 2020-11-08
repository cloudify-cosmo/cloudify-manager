#! /bin/bash -e

virtualenv --python=/usr/bin/python2.7 old_cfy_env
source old_cfy_env/bin/activate
pip install cloudify==${client_version}
python ${python_script_path}
