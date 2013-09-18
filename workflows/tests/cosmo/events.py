from __future__ import absolute_import
from celery.utils.log import get_task_logger
import bernhard
import json

__author__ = 'idanmo'

logger = get_task_logger(__name__)


def get_cosmo_properties():
    """
    Mock.
    """
    return dict()


def set_reachable(node_id):
    """
    Sends a riemann event which causes the state cache to set the node's reachable state
    to true.
    """
    logger.info("Setting {0} reachable state to 'true'".format(node_id))
    riemann_client = bernhard.Client(host="localhost")
    event = {
        "host": node_id,
        "service": "reachable",
        "state": "true",
        "tags": ["cosmo"],
        "description": json.dumps({
            "node_id": node_id,
            "policy": "",
            "message": ""
        })
    }
    riemann_client.send(event)

