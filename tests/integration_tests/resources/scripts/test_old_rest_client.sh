#! /bin/bash -e

virtualenv old_cfy_env
source old_cfy_env/bin/activate
pip install cloudify==${client_version}
python ${python_script_path}
