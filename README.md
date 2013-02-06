Service Grid 2.0
================

The Service Grid 2.0 project is a clean slate implementation for deployment and monitoring orchestration of services installed on the cloud.
It is a clean rewrite of Service Grid 1.0 which is the heart of the Cloudify project.

Service Grid Overview
--------------------------------
SG contains the following components:

* Capacity Planner - Monitors the services and scales the services based on scaling rules. Provides the deployment planner with the desired service capacity.
* Deployment Planner - Maps services to machines, based on the capacity requirements of each service.
* Orchestrator - Sends command to start machines/agents/services according to deployment plan.
* Machine Provisioner - Starts new machines and installs the agent on them.
* Agent - Starts services and uploads service deployment state and service monitoring


Flow Diagram:

          +-----------------------------------------------+------------------------------------+ 
          |                                               |                                    |
     (monitoring)                                      (state)                                 |
          |                                               |                                    |
          V                                               V                                    |
      CAPACITY -(cap.plan)-> DEPLOYMENT -(dep.plan)-> ORCHESTRATOR -(start service)-> AGENTS --+
      PLANNER                 PLANNER                        |                          ^
                                                             |                          |
                                                             |                      (installs)
                                                             |                          |
                                                             |                       MACHINE
                                                             +-------------------->  PROVISIONER

Install Service
---------------
request:

    POST http://localhost/services/tasks/_new_task HTTP 1.1
    {
      "task" : "install_service_task",
      "display_name" : "tomcat",
      "planned_number_of_instances" : 1,
      "max_number_of_instances" : 2,
      "min_number_of_instances" : 1,
	  "service_id" : "http://localhost/services/tomcat/",
      "routing" : {
            "producer_timestamp" : 1359883165467,
            "producer_id" : "http://localhost/webui/",
            "consumer_id" : "http://localhost/services/deployment_planner/",
      }
    }

response:

    HTTP/1.1 202 Accepted

Get Service State
-----------------
request:
    
    GET /services/tomcat/ HTTP 1.1

response:
    
    HTTP/1.1 200 Ok
    ETag: 050e0272361955766459a7beac9e0e41
    {
      "display_name" : "tomcat",
      "planned_number_of_instances" : 1,
      "max_number_of_instances" : 2,
      "min_number_of_instances" : 1,
      "service_id" : "http://localhost/services/tomcat/",
      "progress" : "SERVICE_INSTALLED",
      "instance_ids" : [ "http://localhost/services/tomcat/instances/0/" ],
      "tasks_history" : "/services/tomcat/_tasks_history"
    }

Get Service Instance State
--------------------------
request:

    GET /services/tomcat/instances/0/ HTTP 1.1

response:

    HTTP/1.1 200 Ok
    ETag: 7aa2ce4d898c43403ce64ed7ccb20aa6
    {
      "progress" : "INSTANCE_STARTED",
      "agent_id" : "http://localhost/agents/0/",
      "service_id" : "http://localhost/services/tomcat/",
	  "tasks_history" : "http://localhost/tomcat/instances/0/_tasks_history"
    }


Get Agent State
---------------
request:

    GET /agents/0/ HTTP 1.1

response:

    HTTP/1.1 200 Ok
    ETag: f83dd0858ab524e07e7b5e1f770284c9
    {
      "progress" : "AGENT_STARTED",
      "service_instance_ids" : [ "http://localhost/services/tomcat/instances/0/" ],
      "number_of_agent_restarts" : 0,
      "number_of_machine_restarts" : 0,
      "last_ping_source_timestamp" : 1359930594006,
      "tasks_history" : "http://localhost/agents/0/_tasks_history"

Get Service History
-------------------

request:

    GET /services/tomcat/_tasks_history HTTP 1.1

response:

    HTTP/1.1 200 Ok
    [ {
        "task" : "plan_service_task",
        "state_id" : "http://localhost/services/tomcat/",
        "display_name" : "tomcat",
        "planned_number_of_instances" : 1,
        "max_number_of_instances" : 2,
        "min_number_of_instances" : 1,
        "service_id" : "http://localhost/services/tomcat/",
        "service_instance_ids" : [ "http://localhost/services/tomcat/instances/0/" ],
        "routing" : {
            "producer_timestamp" : 1359883166006,
            "producer_id" : "http://localhost/services/orchestrator/",
            "consumer_id" : "http://localhost/services/orchestrator/"
        }
      }, {
        "task" : "service_installed_task",
        "routing" : {
            "producer_timestamp" : 1359883203007,
            "producer_id" : "http://localhost/services/orchestrator/",
            "consumer_id" : "http://localhost/services/orchestrator/",
            "state_id" : "http://localhost/services/tomcat/"
        }
      } ]

Get Service Instance History
----------------------------

request:

    GET /services/tomcat/instances/0/_tasks_history HTTP 1.1

response:

    HTTP/1.1 200 Ok
    [ {
      "task" : "plan_service_instance_task",
      "service_id" : "http://localhost/services/tomcat/",
      "agent_id" : "http://localhost/agents/0/",
      "routing" : {
          "producer_timestamp" : 1359883197005,
          "producer_id" : "http://localhost/services/orchestrator/",
          "consumer_id" : "http://localhost/services/orchestrator/",
          "state_id" : "http://localhost/services/tomcat/instances/0/"
      }
    }, {
      "task" : "install_service_instance_task",
      "routing" : {
          "producer_timestamp" : 1359883201007
          "producer_id" : "http://localhost/services/orchestrator/",
          "consumer_id" : "http://localhost/agents/0/",
          "state_id" : "http://localhost/services/tomcat/instances/0/"
      }
    }, {
      "task" : "start_service_instance_task",
	  "routing" : {
      "producer_timestamp" : 1359883202007,
	      "producer_id" : "http://localhost/services/orchestrator/",
		  "consumer_id" : "http://localhost/agents/0/",	
          "state_id" : "http://localhost/services/tomcat/instances/0/"
	  }
    } ]

Get Agent History
-----------------
request:
    
    GET /agents/0/_tasks_history HTTP 1.1

response:

    HTTP/1.1 200 Ok
    [ {
        "task" : "plan_agent_task",
        "consumer_id" : "http://localhost/services/orchestrator/",
        "producer_id" : "http://localhost/services/orchestrator/",
        "producer_timestamp" : 1359930530005,
        "state_id" : "http://localhost/agents/0/",
        "service_instance_ids" : [ "http://localhost/services/tomcat/instances/0/" ]
      }, {
        "task" : "start_machine_task",
        "consumer_id" : "http://localhost/services/provisioner/",
        "producer_id" : "http://localhost/services/orchestrator/",
        "producer_timestamp" : 1359930531005,
        "state_id" : "http://localhost/agents/0/"
      }, {
        "task" : "start_agent_task",
        "consumer_id" : "http://localhost/services/provisioner/",
        "producer_id" : "http://localhost/services/orchestrator/",
        "producer_timestamp" : 1359930532005,
        "state_id" : "http://localhost/agents/0/"
      } ]
    }
