Service Grid 2.0
================

The Service Grid 2.0 project is a clean slate implementation for deployment and monitoring orchestration of services installed on the cloud.
It is a clean rewrite of Service Grid 1.0 which is the heart of the Cloudify project.

Service Grid Management Overview
--------------------------------
The SG management contains three components

* Deployment Planner - Maps services to machines, based on the capacity requirements of each service.
* Orchestrator - Deploys and monitors the services according to deployment plan.
* Capacity Planner - Monitors the services and changes the capacity requirements of services
* Agent - Uploads service deployment progress and service monitoring progress

```
      +-----------------------------+-------------------+ 
      |                             |                   |
 (monitoring)                    (state)                |
      |                             |                   |
      V                             V                   |
  capacity --> deployment --> orchestrator --> agents --+
  planner      planner

```

Install Service
---------------
request:
```
POST /service/deployment_planner/tasks HTTP/1.1

Content-Type: application/json
Host: localhost

{
    "task" : "install_service_task"
    "service_config": {
        "display_name": "tomcat",
        "planned_number_of_instances": 1,
        "max_number_of_instances": 2,
        "min_number_of_instances": 1,
        "service_id": "http://localhost/services/tomcat/"
    }
}
```

response:
```
HTTP/1.1 201 Created
Location : "http://localhost/services/deployment_planner/tasks/0"
```