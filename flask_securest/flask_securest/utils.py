import importlib


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


def get_class_instance(class_path, *args, **kwargs):
    """Returns an instance of a class from a string formatted as module:class
    the given *args, **kwargs are passed to the instance's __init__"""

    clazz = get_class(class_path)
    return clazz(*args, **kwargs)


def get_instance_class_fqn(instance):
    instance_cls = instance.__class__
    return instance_cls.__module__ + '.' + instance_cls.__name__


def get_class_fqn(clazz):
    return clazz.__module__ + '.' + clazz.__name__