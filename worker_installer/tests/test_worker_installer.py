__author__ = 'elip'

from worker_installer.tasks import get_machine_ip


def test_get_machine_ip():
    cloudify_runtime = {
        "test_id": {
            "ip": "10.0.0.1"
        }
    }
    ip = get_machine_ip(cloudify_runtime)
    assert ip == "10.0.0.1"