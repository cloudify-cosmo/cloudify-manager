import logging
import logging.handlers
from typing import Sequence


DEFAULT_LOG_PATH = '/var/log/cloudify/rest/cloudify-manager-service.log'
DEFAULT_LOG_LEVEL = 'INFO'


def setup_logger(
        path: str = DEFAULT_LOG_PATH,
        level: str = DEFAULT_LOG_LEVEL,
        warnings: Sequence = None) -> logging.Logger:
    logger = logging.getLogger('manager_service')
    handlers = [
        logging.handlers.WatchedFileHandler(filename=path)
    ]
    _setup_python_logger(
        logger=logger,
        level=level,
        handlers=handlers
    )
    for w in warnings or []:
        logger.warning(w)
    return logger


def _setup_python_logger(
        logger: logging.Logger,
        level: str = DEFAULT_LOG_LEVEL,
        handlers: Sequence[logging.Handler] = None) -> logging.Logger:
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%d/%m/%Y %H:%M:%S')
    for handler in handlers or []:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
