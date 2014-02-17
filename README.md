## Cloudify Cosmo  Manager

Cosmo is the code name for the new release of Cloudify (version 3.0). Cloudify is an open soruce tool for deploying, managing and scaling applications on the cloud. 
This repo contains the source code for the Cloudify Cosmo management server. 
To install Cloudify Cosmo refer the [README file of the Cloudify Cosmo CLI project](https://github.com/CloudifySource/cosmo-cli/blob/develop/README.md). 

Fuller documentation for the new Cosmo architecture will be available soon at [The CloudifySource web site](http://www.cloudifysource.org). 


## Contribute to Cosmo ##

You will need Maven and Git in order to develop the cosmo project.

- Open a new bug or feature request in [JIRA](cloudifysource.atlassian.net) with the "cosmo" label

- clone this repo

```
cosmo-manager$ git clone https://github.com/CloudifySource/cosmo-manager.git
```

- make changes on a seperate branch named `feature/CLOUDIFY-XXXX` where XXXX is the JIRA ID.

- Run unit tests

```
cosmo-manager$ mvn test -f travis-pom.xml
```
    
- Run integration test

```
cosmo-manager        $ cd vagrant
cosmo-manager/vagrant$ python2.7 test/dsl_test.py
```

- Open a new pull request with the changes.
- 
