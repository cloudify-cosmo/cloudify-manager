#!/usr/bin/env python
from pprint import pformat

from .components import cli
from .components import java
from .components import nginx
from .components import stage
from .components import sanity
from .components import consul
from .components import python
from .components import manager
from .components import riemann
from .components import composer
from .components import logstash
from .components import rabbitmq
from .components import influxdb
from .components import syncthing
from .components import mgmtworker
from .components import postgresql
from .components import restservice
from .components import manager_ip_setter

from .components.globals import set_globals
from .components.validations import validate_machine

from .config import config
from .logger import get_logger


logger = get_logger('Bootstrap')

COMPONENTS = [
    manager,
    manager_ip_setter,
    # influxdb,
    nginx,
    python,
    rabbitmq,
    postgresql,
    riemann,
    java,
    consul,
    syncthing,
    stage,
    composer,
    logstash,
    restservice,
    mgmtworker,
    cli,
    sanity
]


def main():
    logger.info('Starting Bootstrap')
    # validate_machine()
    set_globals()

    for component in COMPONENTS:
        component.run()

    logger.debug(pformat(config))
    logger.info('Bootstrap complete!')


if __name__ == '__main__':
    main()
