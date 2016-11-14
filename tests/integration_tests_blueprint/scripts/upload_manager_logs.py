
import os
import sys
import shutil
import tempfile
import subprocess

from manager_rest.utils import mkdirs


S3_URI = 's3://cloudify-tests-logs/'
LINK_PREFIX = 'http://cloudify-tests-logs.s3.amazonaws.com/'
SKIP_FILES = ['journalctl.log']


def _make_links_file(build, root_dir, links):
    for test in links:
        lines = ['<ul>\n']
        for link in links[test]:
            address = LINK_PREFIX + link
            if address.endswith('.log'):
                address += '.txt'
            title = os.path.join(*link.split('/')[3:])
            lines.append('    <li><a href="{0}">{1}</a></li>\n'.format(
                address, title))
        lines.append('</ul>\n')
        with open(os.path.join(root_dir, build, test, 'links.html'), 'w') as f:
            f.writelines(lines)


def _set_local_dir(target_dir, logs_dir, build):
    links = {}
    for root, dirs, files in os.walk(logs_dir):
        for log_file in files:
            if log_file in SKIP_FILES:
                continue
            abs_path = os.path.join(root, log_file)
            rel_path = abs_path.replace(logs_dir, '').strip('/').split('/')
            test_dir = '{0}-{1}-{2}'.format(build, rel_path[0], rel_path[1])
            rel_target = os.path.join(build, test_dir, *rel_path[2:])
            abs_target = os.path.join(target_dir, rel_target)
            if abs_target.endswith('.log'):
                abs_target += '.txt'
            mkdirs(os.path.join('/', *abs_target.split('/')[:-1]))
            shutil.copy(abs_path, abs_target)
            links.setdefault(test_dir, []).append(rel_target)
    return links


def _upload_to_s3(s3_uri, local_dir):
    with open(os.devnull, 'w') as null_out:
        subprocess.check_call(['aws', 's3', 'sync', local_dir, s3_uri,
                               '--content-type', 'text/plain'],
                              stdout=null_out)


def main(s3_uri, logs_dir, build):
    tmp_dir = tempfile.mkdtemp()
    try:
        _make_links_file(build, tmp_dir,
                         _set_local_dir(tmp_dir, logs_dir, build))
        _upload_to_s3(s3_uri, tmp_dir)
    except BaseException:
        raise
    finally:
        shutil.rmtree(tmp_dir)


if __name__ == '__main__':

    logs_path = os.environ.get('CFY_LOGS_PATH')
    if not logs_path:
        print 'The environment variable "CFY_LOGS_PATH" is not specified'
        exit(1)

    if len(sys.argv) < 2:
        print 'Usage: python upload_manager_logs.py JENKINS_BUILD_NUMBER'
        exit(1)

    main(s3_uri=S3_URI,
         logs_dir=os.path.expanduser(logs_path),
         build=sys.argv[1])
