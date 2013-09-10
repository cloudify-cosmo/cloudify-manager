import logging

__author__ = 'elip'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def get_logger(name):
    logger = logging.getLogger(name)
    logger.level = logging.DEBUG
    return logger
