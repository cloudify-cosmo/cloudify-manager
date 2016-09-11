import sys
import logging

from flask import current_app, request
from logging.handlers import RotatingFileHandler

from manager_rest import config


def setup_logger(logger, logger_name):
    """Setup the Flask app's logger

    :param logger: Flask app's logger
    :param logger_name: Name of the logger
    """
    cfy_config = config.instance

    # setting up the app logger with a rotating file handler, in addition to
    #  the built-in flask logger which can be helpful in debug mode.
    additional_log_handlers = [
        RotatingFileHandler(
            filename=cfy_config.rest_service_log_path,
            maxBytes=cfy_config.rest_service_log_file_size_MB * 1024 * 1024,
            backupCount=cfy_config.rest_service_log_files_backup_count
        )
    ]

    _setup_python_logger(
        logger_name=logger_name,
        logger_level=cfy_config.rest_service_log_level,
        handlers=additional_log_handlers,
        remove_existing_handlers=False
    )

    # log all warnings passed to function
    for w in cfy_config.warnings:
        logger.warning(w)


def log_request():
    # form and args parameters are "multidicts", i.e. values are not
    # flattened and will appear in a list (even if single value)
    form_data = request.form.to_dict(False)
    # args is the parsed query string data
    args_data = request.args.to_dict(False)
    # json data; other data (e.g. binary) is available via request.data,
    #  but is not logged
    json_data = request.json if hasattr(request, 'json') else None

    # content-type and content-length are already included in headers

    current_app.logger.debug(
        '\nRequest ({0}):\n'
        '\tpath: {1}\n'
        '\thttp method: {2}\n'
        '\tjson data: {3}\n'
        '\tquery string data: {4}\n'
        '\tform data: {5}\n'
        '\theaders: {6}'.format(
            id(request),
            request.path,  # includes "path parameters"
            request.method,
            json_data,
            args_data,
            form_data,
            _headers_pretty_print(request.headers)))


def log_response(response):
    # content-type and content-length are already included in headers
    # not logging response.data as volumes are massive

    current_app.logger.debug(
        '\nResponse ({0}):\n'
        '\tstatus: {1}\n'
        '\theaders: {2}'
        .format(
            id(request),
            response.status,
            _headers_pretty_print(response.headers)))
    return response


def _headers_pretty_print(headers):
    pp_headers = ''.join(['\t\t{0}: {1}\n'.format(k, v) for k, v in headers])
    return '\n' + pp_headers


def _setup_python_logger(
        logger_name,
        logger_level=logging.DEBUG,
        handlers=None,
        remove_existing_handlers=True
):
    """
    :param logger_name: Name of the logger.
    :param logger_level: Level for the logger (not for specific handler).
    :param handlers: An optional list of handlers (formatter will be
                     overridden); If None, only a StreamHandler for
                     sys.stdout will be used.
    :param remove_existing_handlers: Determines whether to remove existing
                                     handlers before adding new ones
    :return: A logger instance.
    :rtype: Logger
    """

    logger = logging.getLogger(logger_name)

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
