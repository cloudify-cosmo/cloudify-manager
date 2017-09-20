import sys
from os.path import join

import logging

from .config import config
from .constants import CLOUDIFY_BOOTSTRAP_DIR

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)

# The background is set with 40 plus the number of the color,
# and the foreground with 30

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[0;%dm"
BOLD_SEQ = "\033[1;%dm"


LEVEL_COLORS = {
    'WARNING': BOLD_SEQ % YELLOW,
    'INFO': BOLD_SEQ % WHITE,
    'NOTICE': BOLD_SEQ % GREEN,
    'DEBUG': BOLD_SEQ % BLUE,
    'CRITICAL': BOLD_SEQ % YELLOW,
    'ERROR': BOLD_SEQ % RED
}

MSG_LEVEL_COLORS = {
    'WARNING': COLOR_SEQ % YELLOW,
    'INFO': COLOR_SEQ % WHITE,
    'NOTICE': COLOR_SEQ % GREEN,
    'DEBUG': COLOR_SEQ % BLUE,
    'CRITICAL': COLOR_SEQ % YELLOW,
    'ERROR': COLOR_SEQ % RED
}

FORMAT_MESSAGE = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


# region notice log level

# Custom code that adds another log level (notice) in a green color
NOTICE_LOG_LEVEL = 25
logging.addLevelName(NOTICE_LOG_LEVEL, 'NOTICE')


def notice(self, message, *args, **kws):
    if self.isEnabledFor(NOTICE_LOG_LEVEL):
        self._log(NOTICE_LOG_LEVEL, message, args, **kws)


logging.Logger.notice = notice

# endregion


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_color = LEVEL_COLORS[record.levelname]
        msg_color = MSG_LEVEL_COLORS[record.levelname]
        record.levelname = level_color + record.levelname + RESET_SEQ
        record.name = BOLD_SEQ % BLUE + record.name + RESET_SEQ
        record.msg = msg_color + record.msg + RESET_SEQ
        return logging.Formatter.format(self, record)


def _setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # The handler that outputs to file always outputs DEBUG
    fh = logging.FileHandler(join(CLOUDIFY_BOOTSTRAP_DIR, 'log.txt'))
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(FORMAT_MESSAGE))
    logger.addHandler(fh)

    # The console log level is determined by the user in the config
    log_level = config['log_level'].upper()
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(log_level)
    sh.setFormatter(ColoredFormatter(FORMAT_MESSAGE))
    logger.addHandler(sh)


_setup_logger()


def get_logger(logger_name):
    return logging.getLogger('[{0}]'.format(logger_name.upper()))
