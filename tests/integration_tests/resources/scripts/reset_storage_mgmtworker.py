import os
import shutil


def clean_dirs():
    dirs_to_clean = [
        '/opt/mgmtworker/work/deployments',
        # nonexistent dirs will be skipped.
        # these will be present on an AIO
        '/opt/mgmtworker/env/plugins',
        '/opt/mgmtworker/env/source_plugins',
        # ...and these will be on a distributed manager
        '/usr/local/plugins',
        '/usr/local/source_plugins',
    ]
    for directory in dirs_to_clean:
        if not os.path.isdir(directory):
            continue
        for item in os.listdir(directory):
            full_item = os.path.join(directory, item)
            if os.path.isdir(full_item):
                shutil.rmtree(full_item)
            else:
                os.unlink(full_item)


if __name__ == '__main__':
    clean_dirs()
