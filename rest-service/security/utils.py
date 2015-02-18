import importlib
import traceback
import StringIO
from flask import globals as flask_globals
from flask.ext.restful import abort


def get_class(class_path):
    """Returns a class from a string formatted as module:class"""
    if not class_path:
        raise Exception('class path is missing or empty')

    if not isinstance(class_path, basestring):
        raise Exception('class path is not a string')

    class_path = class_path.strip()
    if ':' not in class_path or class_path.count(':') > 1:
        raise Exception('Invalid class path, expected format: '
                        'module:class')

    class_path_parts = class_path.split(':')
    class_module_str = class_path_parts[0].strip()
    class_name = class_path_parts[1].strip()

    if not class_module_str or not class_name:
        raise Exception('Invalid class path, expected format: '
                        'module:class')

    module = importlib.import_module(class_module_str)
    if not hasattr(module, class_name):
        raise Exception('module "{0}", does not contain class "{1}"'
                        .format(class_module_str, class_name))

    return getattr(module, class_name)

'''
def abort_error(error):

    current_app = flask_globals.current_app
    current_app.logger.info('{0}: {1}'.format(type(error).__name__, str(error)))

    s_traceback = StringIO.StringIO()
    traceback.print_exc(file=s_traceback)

    abort(error.http_code,
          message=str(error),
          error_code=error.error_code,
          server_traceback=s_traceback.getvalue())
'''
