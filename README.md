Service Grid 2.0
================

The Service Grid 2.0 project is a clean slate implementation for deployment and monitoring orchestration of services installed on the cloud.
It is a clean rewrite of Service Grid 1.0 which is the heart of the Cloudify project.

Service Grid Management Overview
--------------------------------
The SG management contains three components

Deployment Planner - Maps services to machines, based on the capacity requirements of each service.
Orchestrator - Deploys and monitors the services according to deployment plan.
Capacity Planner - Monitors the services and changes the capacity requirements of services
Agent - Uploads service deployment progress and service monitoring progress

```
      +------------------------------------------------+---------------------+ 
      |                                                |                     |
 (monitoring)                                       (state)                  |
      |                                                |                     |
      V                                                V                     |
  Capacity --(capacity)--> Deployment --(plan)--> Orchestrator --(tasks)--> agents
  Planner                  Planner

```