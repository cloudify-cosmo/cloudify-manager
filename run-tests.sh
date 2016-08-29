#!/bin/bash -e

test_system_workflows()
{
    echo "### Testing rest-service with V2.1 client..."
    pushd workflows && tox && popd
}

test_rest_service_v2_1()
{
    echo "### Testing rest-service with V2.1 client..."
    pushd rest-service && tox -e clientV2_1 && popd
}

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
    test-rest-service-v2_1-client ) test_rest_service_v2_1;;
    test-rest-service-v2-client   ) test_rest_service_v2;;
    test-rest-service-v1-client   ) test_rest_service_v1;;
    flake8                        ) run_flake8;;
    test-system-workflows         ) test_system_workflows;;
esac
