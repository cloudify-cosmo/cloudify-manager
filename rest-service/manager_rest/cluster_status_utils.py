from datetime import datetime
from enum import StrEnum
from typing import Any

from cloudify.cluster_status import CloudifyNodeType
from flask import current_app
from pydantic import BaseModel

from manager_rest.config import instance as config
from manager_rest.prometheus_client import query as prometheus_query

QUERY_STRINGS = {
    CloudifyNodeType.DB: "(postgres_healthy) or (postgres_service)",
    CloudifyNodeType.BROKER: "(rabbitmq_healthy) or (rabbitmq_service)",
    CloudifyNodeType.MANAGER: "(manager_healthy) or (manager_service)",
}

JOB_ASSIGNMENTS = {
    CloudifyNodeType.DB: [
        "postgresql-metrics",
    ],
    CloudifyNodeType.BROKER: [
        "rabbitmq-metrics",
    ],
}

SERVICE_ASSIGNMENTS = {
    CloudifyNodeType.DB: [
        "postgresql",
    ],
    CloudifyNodeType.BROKER: [
        "rabbitmq",
    ],
    CloudifyNodeType.MANAGER: [
        "api-service",
        "rest-service",
        "execution-scheduler",
        "mgmtworker",
        "composer-backend",
        "composer-frontend",
        "stage-backend",
        "stage-frontend",
        "nginx",
        "prometheus-server",
    ],
}

STATUS = "status"


class Status(StrEnum):
    FAIL = "Fail"
    OK = "OK"
    UNKNOWN = "Unknown"


class Metric(BaseModel):
    healthy: bool
    last_check: str | None
    metric_name: str | None
    metric_type: str | None
    service_name: str | None


class Node(BaseModel):
    private_ip: str | None
    public_ip: str | None
    version: str | None
    metrics: list[Metric] | None
    failures: list[str] | None = None
    status: Status

    def calc_status(self):
        self.status = (
            Status.OK
            if all(m.healthy for m in self.metrics) and not self.failures
            else Status.FAIL
        )


class Service(BaseModel):
    is_external: bool = False
    nodes: dict[str, Node] = {}
    failures: list[str] | None = None
    status: Status

    def calc_status(self, in_depth=True):
        if in_depth:
            for node_name in self.nodes:
                self.nodes[node_name].calc_status()
        self.status = (
            Status.OK
            if all(n.status for n in self.nodes.values()) and not self.failures
            else Status.FAIL
        )


class ClusterStatus(BaseModel):
    status: Status = Status.FAIL
    services: dict[str, Service] = {}

    def calc_status(self, in_depth=True):
        if in_depth:
            for service_name in self.services:
                self.services[service_name].calc_status(in_depth)
        self.status = (
            Status.OK
            if all(s.status for s in self.services.values())
            else Status.FAIL
        )
        return self

    def populate_prometheus_metrics(self, prometheus_results: list[dict]):
        for result in prometheus_results:
            service_assignment, instance, node = parse_metrics(result)
            if not service_assignment:
                continue
            if service_assignment not in self.services:
                self.services[service_assignment] = Service(
                    is_external=False,
                    nodes={instance: node},
                    status=Status.OK,
                )
            elif instance not in self.services[service_assignment].nodes:
                self.services[service_assignment].nodes[instance] = node
        return self

    def fill_missing_services(self, service_assignments: dict[str, list[str]]):
        for service_assignment, service_names in service_assignments.items():
            if service_assignment not in self.services:
                self.services[service_assignment] = Service(
                    is_external=False,
                    nodes={},
                    status=Status.FAIL,
                    failures=[
                        f"Missing metrics for {service_name}"
                        for service_name in service_names
                    ],
                )
            else:
                nodes = self.services[service_assignment].nodes
                for service_name in service_names:
                    found = False
                    for node_name, node in nodes.items():
                        for metric in node.metrics:
                            if metric.service_name == service_name:
                                found = True
                                break
                        if found:
                            break
                    if not found:
                        self.mark_service_not_found(
                            service_assignment, service_name
                        )
        return self

    def mark_service_not_found(self, node_type: str, service_name: str):
        if node_type in {
            CloudifyNodeType.BROKER,
            CloudifyNodeType.DB,
        }:
            self.services[node_type].is_external = True
            self.services[node_type].status = Status.UNKNOWN
        else:
            if self.services[node_type].failures is None:
                self.services[node_type].failures = []
            self.services[node_type].failures.append(
                f"Missing metrics for service {service_name}"
            )
            self.services[node_type].status = Status.FAIL


def get_cluster_status() -> dict[str, Any]:
    query_string = ' or '.join(QUERY_STRINGS.values())
    prometheus_results = prometheus_query(
        query_string=query_string,
        logger=current_app.logger,
        timeout=config.monitoring_timeout,
    )
    status = (
        ClusterStatus()
        .populate_prometheus_metrics(prometheus_results)
        .fill_missing_services(SERVICE_ASSIGNMENTS)
        .calc_status()
    )
    return status.dict(exclude_none=True)


def service_node_type(
    service_name: str | None,
    job_name: str | None,
) -> str | None:
    for node_type, service_names in SERVICE_ASSIGNMENTS.items():
        if service_name in service_names:
            return node_type
    for node_type, job_names in JOB_ASSIGNMENTS.items():
        if job_name in job_names:
            return node_type


def parse_metrics(result: dict) -> (str | None, str | None, Node | None):
    raw_metric = result.get("metric", {})
    host = raw_metric.get("host")
    instance = raw_metric.get("instance")
    job = raw_metric.get('job', '')
    if (
        not (
            service_name := raw_metric.get("deployment")
            or raw_metric.get("statefulset")
        )
        and instance
        and (namespace := raw_metric.get("namespace"))
    ):
        service_name, _, _ = instance.partition(f".{namespace}.")
        if service_name.endswith("-metrics"):
            service_name = service_name[:-8]

    service_assignment = service_node_type(service_name, job)
    if not service_assignment:
        return None, None, None

    timestamp, healthy = result.get("value", [0, ""])
    healthy = bool(int(healthy)) if healthy else False
    metric_name = raw_metric.get("__name__")
    if instance:
        metric_name += f" ({instance})"
    return (
        service_assignment,
        service_name,
        Node(
            private_ip=host or service_name,
            public_ip=service_name,
            metrics=[
                Metric(
                    healthy=healthy,
                    last_check=last_check_from_timestamp(timestamp),
                    metric_name=metric_name,
                    metric_type=job,
                    service_name=service_name,
                )
            ],
            failures=(
                [f"Unhealthy service {service_name}"] if not healthy else None
            ),
            status=Status.OK if healthy else Status.FAIL,
        ),
    )


def last_check_from_timestamp(ts: float | None) -> str:
    if ts:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return "unknown"
