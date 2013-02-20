Cloudify Cosmo Management
=========================

The Cloudify Cosmo project is a clean slate implementation for deployment and monitoring orchestration of services 
installed on the cloud.
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
