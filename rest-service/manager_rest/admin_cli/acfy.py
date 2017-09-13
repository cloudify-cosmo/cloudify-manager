
import click

from . import helptexts


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())


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


class Options(object):
    def __init__(self):
        # put options here
        pass

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
