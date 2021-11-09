import sys
import logging

from flask import current_app, request
from logging.handlers import WatchedFileHandler

from manager_rest import config


def setup_logger(logger):
    """Setup the Flask app's logger

    :param logger: Flask app's logger
    """
    cfy_config = config.instance

    # setting up the app logger with a watched file handler, in addition to
    #  the built-in flask logger which can be helpful in debug mode.
    # log rotation is handled by logrotate.
    additional_log_handlers = [
        WatchedFileHandler(
            filename=cfy_config.rest_service_log_path
        )
    ]

    _setup_python_logger(
        logger=logger,
        logger_level=cfy_config.rest_service_log_level,
        handlers=additional_log_handlers,
        remove_existing_handlers=False
    )

    # log all warnings passed to function
    for w in cfy_config.warnings:
        logger.warning(w)


def log_request():
    # args is the parsed query string data
    args_data = request.args.to_dict(False)

    # content-type and content-length are already included in headers
    current_app.logger.debug(
        '\nRequest (%s):\n'
        '\tpath: %s\n'
        '\thttp method: %s\n'
        '\tquery string data: %s',
        id(request),
        request.path,  # includes "path parameters"
        request.method,
        args_data,
    )


def log_response(response):
    # content-type and content-length are already included in headers
    # not logging response.data as volumes are massive

    current_app.logger.debug(
        '\nResponse (%s):\n'
        '\tstatus: %s',
        id(request),
        response.status,
    )
    return response


def _setup_python_logger(
        logger,
        logger_level=logging.DEBUG,
        handlers=None,
        remove_existing_handlers=True
):
    """
    :param logger: The flask app logger
    :param logger_level: Level for the logger (not for specific handler).
    :param handlers: An optional list of handlers (formatter will be
                     overridden); If None, only a StreamHandler for
                     sys.stdout will be used.
    :param remove_existing_handlers: Determines whether to remove existing
                                     handlers before adding new ones
    :return: A logger instance.
    :rtype: Logger
    """

    if remove_existing_handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    if not handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handlers = [handler]

    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%d/%m/%Y %H:%M:%S')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logger_level)
    return logger
