#!/bin/bash -e

test_rest_service_v2()
{
    echo "### Testing rest-service with V2 client..."
    pushd rest-service && tox -e clientV2 && popd
}

test_rest_service_v1()
{
    echo "### Testing rest-service V1 client..."
    pushd rest-service && tox -e clientV1 && popd
}

run_intergration_tests()
{
    echo "### Running integration tests..."
    sudo apt-get update && sudo apt-get install -qy python-dbus
    dpkg -L python-dbus
    #sudo ln -sf /usr/lib/python2.7/dist-packages/dbus ~/env/lib/python2.7/site-packages/dbus
    #sudo ln -sf /usr/lib/python2.7/dist-packages/_dbus_*.so ~/env/lib/python2.7/site-packages
    wget https://download.elastic.co/elasticsearch/elasticsearch/elasticsearch-1.6.0.deb
    sudo dpkg -i elasticsearch-1.6.0.deb
    export PATH=/usr/share/elasticsearch/bin:$PATH
    sudo mkdir -p /usr/share/elasticsearch/data
    sudo chmod 777 /usr/share/elasticsearch/data
    wget http://aphyr.com/riemann/riemann_0.2.6_all.deb
    sudo dpkg -i riemann_0.2.6_all.deb
    sudo test -d /dev/shm && sudo rm -rf /dev/shm
    sudo ln -Tsf /{run,dev}/shm
    sudo chmod 777 /dev/shm  # for celery worker

    pip install -r tests/dev-requirements.txt
    pushd rest-service && pip install -r dev-requirements.txt && popd
    pushd rest-service && pip install . && popd

    # make utils and such
    # available as python packages
    pushd plugins/riemann-controller && pip install . && popd
    pushd workflows && pip install . && popd
    pushd tests && pip install -e . && popd

    pip install nose

    SCRIPT=$(readlink -f $0)
    export REPOSITORY_PATH=$(dirname $SCRIPT)
    local config_path=$(mktemp)
    # flags that relate to test collection should follow this command
    # e.g.: -e, -i, etc...
    nosetests \
        tests/workflow_tests \
        --with-suitesplitter \
        --suite-total=${NUMBER_OF_SUITES} \
        --suite-number=${SUITE_NUMBER} \
        --suite-config-path=${config_path}
    # flags that affect test execution should follow this command
    # the generated ${config_path} contains tests that were collected
    # in the previous command
    # e.g. --nocapture, --cov, etc..
    nosetests \
        --nologcapture \
        --nocapture \
        -v -c ${config_path}
}

run_flake8()
{
    echo "### Running flake8..."
    pip install flake8
    flake8 plugins/riemann-controller/
    flake8 workflows/
    flake8 rest-service/
    flake8 tests/
}

case $1 in
    test-rest-service-v2-client ) test_rest_service_v2;;
    test-rest-service-v1-client ) test_rest_service_v1;;
    run-integration-tests       ) run_intergration_tests;;
    flake8                      ) run_flake8;;
esac
