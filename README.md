## Cloudify Cosmo Manager

Cosmo is the code name for the new release of Cloudify (version 3.0). Cloudify is an open soruce tool for deploying, managing and scaling applications on the cloud. 
This repo contains the source code for the Cloudify Cosmo management server. 
To install Cloudify 3.0 refer the [README file of the Cloudify CLI project](https://github.com/cloudify-cosmo/cloudify-cli/blob/develop/README.md). 

Fuller documentation for the new Cosmo architecture will be available soon at [The CloudifySource web site](http://www.cloudifysource.org). 


## Contribute to Cloudify ##

- Open a new bug or feature request in [JIRA](cloudifysource.atlassian.net) under the "CFY" project

- clone this repo

```
cloudify-manager$ git clone https://github.com/cloudify-cosmo/cloudify-manager.git
```

- make changes on a seperate branch named `feature/CFY-XXXX` where XXXX is the JIRA ID.

# Linux Developement Environment #

Development environment was tested with: Ubuntu & Arch Linux.

## Requirements ##

Make sure you have the following dependencies installed:

* git.
* Python 2.7 + pip.
* OpenJDK-7.
* Ruby 2.1.0.
* Bundler.
* RabbitMQ.
    * Make sure you have a default configured RabbitMQ server running after installing it.
* Riemann (http://riemann.io).
    * Make sure Riemann's binary is available in `path` environment variable after installing it.
* Elasticsearch (http://www.elasticsearch.org/)
    * Make sure Elasticsearch's binary is availale in `path` environment variable after installing it, as well as having write permission to its `/data` folder (more information below)
Installation instructions for Ubuntu can be found below, if you're using Arch Linux you should know your way :-)


### git ###

Ubuntu installation:
```
sudo apt-get install git -y
```

### pip ###
Ubuntu installation:
```
sudo apt-get install python-pip -y
```

Arch Linux installation:
```
pacman -S python2-pip
```

### OpenJDK-7 ###

```
sudo apt-get install openjdk-7-jdk
```

### virtualenv ###

We encourage you to use `virtualenv` for the Python environment, this means `virtualenv2` should be installed:
```
# install virtualenv
sudo pip install virtualenv

# create a virtual environment
sudo virtualenv <env_folder>

# activate the virtual environment
source <env_folder>/bin/activate
```

### Ruby 2.1.0 ###

#### Install Using rvm ####
- Install rvm as described [here](http://rvm.io/).
- Install Ruby 2.1.0 using rvm:

```
# install (this might take some time)
rvm install ruby-2.1.0

# use
rvm use ruby-2.1.0

# install bundler
gem install bundler
```

### RabbitMQ ###
Installation instructions for Ubuntu can be found [here](http://www.rabbitmq.com/install-debian.html).

If there are any missing dependencies, this might help:
```
apt-get install build-essential libncurses5-dev openssl libssl-dev fop xsltproc unixodbc-dev
```

### Riemann ###
deb file can be downloaded from: http://riemann.io/.

And then:
```
sudo dpkg -i <riemann_deb_file>
```

### Elasticsearch ###
deb file can be downloaded from: http://www.elasticsearch.org/download
e.g.:  
`wget https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.0.1.deb`  
`sudo dpkg -i elasticsearch-1.0.1.deb`

Path variable must include elasticsearch's bin directory, e.g.:    
`export PATH=$PATH:/usr/share/elasticsearch/bin`

You might need to set write permissions for elasticsearch's data folder:  
`sudo mkdir -p /usr/share/elasticsearch/data`  
`sudo chmod 777 /usr/share/elasticsearch/data`


## Lets Get It Working! ##

So, after we have all the requirements installed, its time to checkout Cloudify's manager source code and install each of its components.

We'll go through the following steps:


* Source code checkout.
* Install `workflow-service` project dependencies.
* Install `rest-service` project dependencies.
* Install `tests` project dependencies.
* Run a sample test.


### Source Code Checkout ###

Clone this repository:
```
mkdir -p ~/dev/cloudify
cd ~/dev/cloudify
git clone https://github.com/cloudify-cosmo/cloudify-manager
cd cloudify-manager
git checkout develop
```

### Install workflow-service Project Dependencies ###

Workflow service is a Sinatra Ruby project which runs on Ruby 2.1.0.
We use `bundler` for installing its dependencies:
```
# in cloudify-manager folder
cd workflow-service
bundle install
```

## Install rest-service Project Dependencies ##

First install dependencies for compiling with Python
```
# sudo apt-get install python-dev -y
```


This project contains Cloudify's manager REST service.
In order to install its dependencies run:
```
# in cloudify-manager folder
cd rest-service
python setup.py install
```

## Install tests Project Dependencies ##

This project is used for running integration tests which use mock Cloudify plugins and mainly used for
testing Cloudify's manager functionality and workflows behavior.

In order to install its dependencies run:
```
# in cloudify-manager folder
cd tests
python setup.py install

# install nose tests
pip install nose
```

## Running Tests ##

A few words about the testing framework.
When launching a test, A Cloudify environment will be created which consists of:

1. RabbitMQ Server (should be manually started).
2. Riemann Server (Riemann binary path should be available in `path` environment variable).
3. Manager's REST Service.
4. Workflow Engine Service.
5. Celery Worker (In tests, all plugins will run on manager's Celery Worker).

The environment will be created once per Python package (different tests in the same Python package will share the same environment - we make sure to clean whatever's needed after each test).

Now that we're set, lets run some basic integration tests (goodluck):
```
# in cloudify-manager folder
cd tests
nosetests workflow_tests/test_workflow.py
```

Hopefully, the tests should pass :-)
