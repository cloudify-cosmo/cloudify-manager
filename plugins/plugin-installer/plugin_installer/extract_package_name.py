"""
hack-ish script to extract the name field from a python package
should be called with the directory containing setup.py as the first argument
"""
if __name__ == '__main__':
    import setuptools
    import sys
    from os import path
    root_dir = sys.argv[1]

    # patch for setuptools.py that prints the package name
    # to stdout (also supports pbr packages)
    def patch_setup(name=None, pbr=False, *args, **kwargs):
        if pbr:
            import ConfigParser
            config = ConfigParser.ConfigParser()
            config.read(path.join(root_dir, 'setup.cfg'))
            name = config.get('metadata', 'name')
        if name is None:
            sys.stderr.write('Failed finding extracting package name for'
                             ' package located at: {0}'.format(root_dir))
            sys.exit(1)
        sys.stdout.write(name)
    # monkey patch setuptools.setup
    setuptools.setup = patch_setup
    # Make sure our setup.py is first in path
    sys.path.insert(0, root_dir)
    # The line below is important
    import setup  # NOQA
