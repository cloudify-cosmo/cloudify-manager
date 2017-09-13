
from . import logger, acfy


@acfy.group(name='acfy')
@acfy.options.verbose(expose_value=True)
@acfy.options.version
def _acfy(verbose):
    logger.set_global_verbosity_level(verbose)


def _register_commands():
    pass


_register_commands()
logger.configure_loggers()


if __name__ == '__main__':
    _acfy()
