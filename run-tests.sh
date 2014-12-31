#!/bin/bash -e

test_plugins()
{
    echo "### Testing plugins..."
    echo "### Creating agent package..."

    mkdir -p package/linux
    virtualenv package/linux/env
    source package/linux/env/bin/activate

    pip install testtools
    pip install celery==3.0.24

    git clone https://github.com/cloudify-cosmo/cloudify-rest-client --depth=1
    cd cloudify-rest-client; pip install .; cd ..

    git clone https://github.com/cloudify-cosmo/cloudify-plugins-common --depth=1
    cd cloudify-plugins-common; pip install .; cd ..

    git clone https://github.com/cloudify-cosmo/cloudify-script-plugin --depth=1
    cd cloudify-script-plugin; pip install .; cd ..

    pushd plugins/agent-installer && pip install . && popd
    pushd plugins/windows-agent-installer && pip install . && popd
    pushd plugins/plugin-installer && pip install . && popd
    pushd plugins/windows-plugin-installer && pip install . && popd
    pushd plugins/agent-installer/worker_installer/tests/mock-sudo-plugin && pip install . && popd
    tar czf Ubuntu-agent.tar.gz package
    rm -rf package

    virtualenv ~/env
    source ~/env/bin/activate

    pip install testtools
    pip install celery==3.0.24
    pip install -r tests/dev-requirements.txt

    pushd plugins/agent-installer && pip install . && popd
    pushd plugins/plugin-installer && pip install . && popd
    pushd plugins/windows-agent-installer; pip install .; popd
    pushd plugins/windows-plugin-installer; pip install .; popd
    pushd plugins/riemann-controller; pip install .; popd

    echo "### Starting HTTP server for serving agent package (for agent installer tests)"
    python -m SimpleHTTPServer 8000 &

    pip install nose
    pip install mock

    nosetests plugins/plugin-installer/plugin_installer/tests --nologcapture --nocapture
    nosetests plugins/windows-plugin-installer/windows_plugin_installer/tests --nologcapture --nocapture
    nosetests plugins/windows-agent-installer/windows_agent_installer/tests --nologcapture --nocapture

    echo "Defaults:travis  requiretty" | sudo tee -a /etc/sudoers
    pushd plugins/agent-installer
    nosetests worker_installer.tests.test_configuration:CeleryWorkerConfigurationTest --nologcapture --nocapture
    nosetests worker_installer.tests.test_worker_installer:TestLocalInstallerCase --nologcapture --nocapture
    popd
}

test_rest_service()
{
    echo "### Testing rest-service..."
    pushd rest-service && pip install . -r dev-requirements.txt && popd
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
    export PATH=/usr/share/elasticsearch/bin:$PATH
    sudo mkdir -p /usr/share/elasticsearch/data
    sudo chmod 777 /usr/share/elasticsearch/data
    wget http://aphyr.com/riemann/riemann_0.2.6_all.deb
    sudo dpkg -i riemann_0.2.6_all.deb
    sudo test -d /dev/shm && sudo rm -rf /dev/shm
    sudo ln -Tsf /{run,dev}/shm
    sudo chmod 777 /dev/shm  # for celery worker

    pip install -r tests/dev-requirements.txt
    pushd rest-service && pip install . -r dev-requirements.txt && popd

    # make utils and such
    # available as python packages
    pushd plugins/riemann-controller && pip install . && popd
    pushd workflows && pip install . && popd
    pushd tests && pip install . && popd

    pip install nose
    nosetests tests/workflow_tests --nologcapture --nocapture -v

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

run_plugin_installer_py26()
{
    pip install tox
    cd plugins/plugin-installer && tox -e py26
}

case $1 in
    test-plugins         ) test_plugins;;
    test-rest-service    ) test_rest_service;;
    run-integration-tests) run_intergration_tests;;
    flake8               ) run_flake8;;
    plugin-installer-py26) run_plugin_installer_py26;;
esac
