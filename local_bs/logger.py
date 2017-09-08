import sys

from logging import getLogger, Formatter, StreamHandler

from .config import config

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
    'DEBUG': BOLD_SEQ % BLUE,
    'CRITICAL': BOLD_SEQ % YELLOW,
    'ERROR': BOLD_SEQ % RED
}

MSG_LEVEL_COLORS = {
    'WARNING': COLOR_SEQ % YELLOW,
    'INFO': COLOR_SEQ % WHITE,
    'DEBUG': COLOR_SEQ % BLUE,
    'CRITICAL': COLOR_SEQ % YELLOW,
    'ERROR': COLOR_SEQ % RED
}


class ColoredFormatter(Formatter):
    def format(self, record):
        level_color = LEVEL_COLORS[record.levelname]
        msg_color = MSG_LEVEL_COLORS[record.levelname]
        record.levelname = level_color + record.levelname + RESET_SEQ
        record.name = BOLD_SEQ % BLUE + record.name + RESET_SEQ
        record.msg = msg_color + record.msg + RESET_SEQ
        return Formatter.format(self, record)


def _setup_logger():
    log_level = config['log_level'].upper()
    logger = getLogger()
    logger.setLevel(log_level)

    ch = StreamHandler(sys.stdout)
    ch.setLevel(log_level)
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


_setup_logger()


def get_logger(logger_name):
    return getLogger('[{0}]'.format(logger_name.upper()))
