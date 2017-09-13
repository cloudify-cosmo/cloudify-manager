
import click
from functools import wraps

from . import helptexts, logger


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())


def pass_context(func):
    """Make click context Cloudify specific

    This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.pass_context(func)


def pass_logger(func):
    """Simply passes the logger to a command."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        new_logger = logger.get_logger()
        return func(logger=new_logger, *args, **kwargs)
    return wrapper


def group(name):
    """Allow to create a group with a default click context
    and a cls for click's `didyoueamn` without having to repeat
    it for every group.
    """
    return click.group(name=name, context_settings=CLICK_CONTEXT_SETTINGS)


def command(*args, **kwargs):
    """Make Click commands Cloudify specific

    This exists purely for aesthetical reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.command(*args, **kwargs)


def argument(*args, **kwargs):
    """Make Click arguments Cloudify specific

    This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.argument(*args, **kwargs)


def show_version(ctx, param, value):
    if value:
        logger.get_logger().info('version')
        ctx.exit()


class Options(object):
    def __init__(self):
        self.version = click.option(
            '--version',
            is_flag=True,
            callback=show_version,
            expose_value=False,
            is_eager=True,
            help=helptexts.VERSION)
        self.node_name = click.option(
            '--node-name',
            help=helptexts.NODE_NAME)
        self.host_ip = click.option(
            '--host-ip',
            help=helptexts.HOST_IP)
        self.manager_username = click.option(
            '-u',
            '--manager-username',
            required=False,
            help=helptexts.MANAGER_USERNAME
        )
        self.manager_password = click.option(
            '-p',
            '--manager-password',
            required=False,
            help=helptexts.MANAGER_PASSWORD)
        self.master_ip = click.option(
            '-m',
            '--master-ip',
            required=True,
            help=helptexts.MASTER_IP)

    @staticmethod
    def verbose(expose_value=False):
        return click.option(
            '-v',
            '--verbose',
            count=True,
            expose_value=expose_value,
            is_eager=True,
            help=helptexts.VERBOSE)


options = Options()
