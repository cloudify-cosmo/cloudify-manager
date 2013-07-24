[![Build Status](https://secure.travis-ci.org/CloudifySource/cosmo-manager.png?branch=develop)](http://travis-ci.org/CloudifySource/cosmo-manager) develop branch

# Cloudify Cosmo Management #

The Cloudify Cosmo Management project is the scafolding for the deployment, monitoring and automatic managing services 
installed on the cloud.


If you want to see it in action, keep reading...

Requirements
============

- Linux/MAC operation system.
- Git
- JAVA runtime 1.7 (openjdk or oracle).
- Python2 with the following packages installed: (Use pip to install)
	- celery
	- fabric
    - vagrant
    - bernhard
- Riemann (http://riemann.io)
- RabbitMQ (http://www.rabbitmq.com/download.html)


Setup
=====

- RabbitMQ process running:	
	- Start RabbitMQ as a service, no configuration is required.


Build
=====

- git clone https://github.com/CloudifySource/cosmo-manager.git
- cd cosmo-manager/orchestrator
- mvn -DskipTests package -Pall