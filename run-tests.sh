#!/bin/bash -e

test_rest_service()
{
    echo "### Testing rest-service..."
    pushd rest-service && pip install -r dev-requirements.txt && popd
    pushd rest-service && pip install . && popd
    pip install nose
    nosetests rest-service/manager_rest/test --nologcapture --nocapture
}

run_intergration_tests()
{
    echo "### Running integration tests..."

    wget https://download.elastic.co/elasticsearch/elasticsearch/elasticsearch-1.6.0.tar.gz
    tar xzvf elasticsearch-1.6.0.tar.gz
    export PATH=$PWD/elasticsearch-1.6.0/bin:$PATH

    wget https://s3-eu-west-1.amazonaws.com/cloudify-test-resources/riemann-0.2.6.tar.bz2
    tar xjvf riemann-0.2.6.tar.bz2
    export PATH=$PWD/riemann-0.2.6/bin:$PATH

    pip install -r tests/dev-requirements.txt
    pushd rest-service && pip install -r dev-requirements.txt && popd
    pushd rest-service && pip install . && popd

    # make utils and such
    # available as python packages
    pushd plugins/riemann-controller && pip install . && popd
    pushd workflows && pip install . && popd
    pushd tests && pip install -e . && popd

    pip install nose

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
    test-rest-service    ) test_rest_service;;
    run-integration-tests) run_intergration_tests;;
    flake8               ) run_flake8;;
esac
