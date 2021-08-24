#!/opt/manager/env/bin/python

"""Truncate audit_log entries"""
import logging
import sys
from datetime import datetime
from os.path import basename

import click
from dateutil import parser
from manager_rest.shell import common
from manager_rest.storage import db


@click.command()
@click.option('-b', '--before',
              help='Remove audit logs from before that timestamp, e.g. '
                   '`truncate-audit-log -b "2021-07-05 22:27"`.')
@click.option('-o', '--older-than',
              help='Remove audit logs older than that interval, e.g. '
                   '`truncate-audit-log -o "2 weeks"`.')
@click.option('-f', '--force', is_flag=True, flag_value=False,
              help="Don't ask for confirmation.")
def main(before, older_than, force):
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)s '
               '[%(module)s.%(funcName)s] %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO)
    logger = logging.getLogger(basename(sys.argv[0]))

    if before:
        timestamp = parser.parse(before)
        if older_than:
            logger.critical('--before and --older-than parameters are '
                            'mutually exclusive.')
            sys.exit(1)
    elif older_than:
        delta = common.parse_time_interval(older_than)
        timestamp = datetime.now() - delta if delta else None
    else:
        timestamp = None

    if not timestamp:
        logger.critical('Please provide either --before or --older-than '
                        'parameter.')
        sys.exit(1)

    if not force:
        if input("Are you sure you want to remove all audit_log entries "
                 f"before {timestamp} [y/N] ? ").lower() != 'y':
            logger.info('Audit log not truncated.')
            sys.exit(0)

    common.setup_environment()
    result = db.session.execute(
        'DELETE FROM audit_log WHERE created_at < :timestamp',
        params={'timestamp': timestamp})
    db.session.commit()

    logger.info('Audit log truncated (%d records removed).', result.rowcount)


if __name__ == '__main__':
    main()
