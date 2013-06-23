[![Build Status](https://secure.travis-ci.org/CloudifySource/cosmo-manager.png?branch=develop)](http://travis-ci.org/CloudifySource/cosmo-manager) develop branch

# Cloudify Cosmo Management #

The Cloudify Cosmo Management project is the scafolding for the deployment, monitoring and automatic managing services 
installed on the cloud.


Cosmo Management contains the following main components:

* Orchestrator - Reacts to service state changes by running custom workflows (uses Ruote)
* Resource Monitor - Continously evaluates service state by reacting to incoming events (uses Drools Fusion).
* Message Broker - Decouples the different components by providing a central messaging endpoint (uses Atmosphere).
