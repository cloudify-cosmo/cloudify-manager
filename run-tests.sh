#!/bin/bash -e

test_plugins()
{
    echo "### Testing plugins..."
    echo "### Creating agent package..."
    mkdir -p package/linux
    virtualenv package/linux/env
    source package/linux/env/bin/activate

    pip install celery==3.0.24

    git clone https://github.com/cloudify-cosmo/cloudify-rest-client --depth=1
    cd cloudify-rest-client; pip install .; cd ..

    git clone https://github.com/cloudify-cosmo/cloudify-plugins-common --depth=1
    cd cloudify-plugins-common; pip install .; cd ..

    cd plugins/agent-installer && pip install . && cd ../..
    cd plugins/windows-agent-installer && pip install . && cd ../..
    cd plugins/plugin-installer && pip install . && cd ../..
    cd plugins/windows-plugin-installer && pip install . && cd ../..
    cd plugins/agent-installer/worker_installer/tests/mock-sudo-plugin && pip install . && cd ../../../../..
    tar czf Ubuntu-agent.tar.gz package
    rm -rf package

    virtualenv ~/env
    source ~/env/bin/activate

    pip install celery==3.0.24
    cd cloudify-rest-client; pip install .; cd ..
    cd cloudify-plugins-common; pip install .; cd ..
    cd plugins/agent-installer && pip install . && cd ../..
    cd plugins/plugin-installer && pip install . && cd ../..
    cd plugins/windows-agent-installer; pip install .; cd ../..
    cd plugins/windows-plugin-installer; pip install .; cd ../..
    cd plugins/riemann-controller; pip install .; cd ../..

    echo "### Starting HTTP server for serving agent package (for agent installer tests)"
    python -m SimpleHTTPServer 8000 &

    pip install nose

    nosetests plugins/plugin-installer/plugin_installer/tests --nologcapture --nocapture
    nosetests plugins/windows-plugin-installer/windows_plugin_installer/tests --nologcapture --nocapture
    nosetests plugins/windows-agent-installer/windows_agent_installer/tests --nologcapture --nocapture

    echo "Defaults:travis  requiretty" | sudo tee -a /etc/sudoers
    cd plugins/agent-installer
    nosetests worker_installer.tests.test_configuration:CeleryWorkerConfigurationTest --nologcapture --nocapture
    nosetests worker_installer.tests.test_worker_installer:TestLocalInstallerCase --nologcapture --nocapture
    cd ..
}

test_rest_service()
{
    echo "### Testing rest-service..."
    git clone https://github.com/cloudify-cosmo/cloudify-rest-client --depth=1
    cd cloudify-rest-client; pip install .; cd ..
    cd rest-service && pip install . -r dev-requirements.txt && cd ..
    pip install nose
    nosetests rest-service/manager_rest/test --nologcapture --nocapture
}

run_intergration_tests()
{
    echo "### Running integration tests..."
    sudo apt-get update && sudo apt-get install -qy python-dbus
    dpkg -L python-dbus
    #sudo ln -sf /usr/lib/python2.7/dist-packages/dbus ~/env/lib/python2.7/site-packages/dbus
    #sudo ln -sf /usr/lib/python2.7/dist-packages/_dbus_*.so ~/env/lib/python2.7/site-packages
    wget https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.3.2.deb
    sudo dpkg -i elasticsearch-1.3.2.deb
    export PATH=$PATH:/usr/share/elasticsearch/bin
    sudo mkdir -p /usr/share/elasticsearch/data
    sudo chmod 777 /usr/share/elasticsearch/data
    wget http://aphyr.com/riemann/riemann_0.2.6_all.deb
    sudo dpkg -i riemann_0.2.6_all.deb
    sudo test -d /dev/shm && sudo rm -rf /dev/shm
    sudo ln -Tsf /{run,dev}/shm
    sudo chmod 777 /dev/shm  # for celery worker

    git clone https://github.com/cloudify-cosmo/cloudify-rest-client --depth=1
    cd cloudify-rest-client; pip install .; cd ..
    git clone https://github.com/cloudify-cosmo/cloudify-plugins-common --depth=1
    cd cloudify-plugins-common; pip install .; cd ..

    cd rest-service && pip install . -r dev-requirements.txt && cd ..

    cd plugins/riemann-controller && pip install . && cd ../..
    cd workflows && pip install . && cd ..
    cd tests && pip install . && cd ..

    pip install nose
    nosetests tests/workflow_tests --nologcapture --nocapture -v
    nosetests tests/deployment_env_tests --nologcapture --nocapture -v
}

run_flake8()
{
    echo "### Running flake8..."
    pip install flake8
    flake8 plugins/agent-installer/
    flake8 plugins/windows-agent-installer/
    flake8 plugins/plugin-installer/
    flake8 plugins/windows-plugin-installer/
    flake8 plugins/riemann-controller/
    flake8 workflows/
    flake8 rest-service/
    flake8 tests/
}

case $1 in
    test-plugins         ) test_plugins;;
    test-rest-service    ) test_rest_service;;
    run-integration-tests) run_intergration_tests;;
    flake8               ) run_flake8;;
esac
