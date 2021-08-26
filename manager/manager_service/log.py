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
    logger.addHandler(_setup_file_handler(path))
    logger.setLevel(level)
    for w in warnings or []:
        logger.warning(w)
    return logger


def _setup_file_handler(path: str) -> logging.handlers.WatchedFileHandler:
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%d/%m/%Y %H:%M:%S')
    handler = logging.handlers.WatchedFileHandler(filename=path)
    handler.setFormatter(formatter)
    return handler
