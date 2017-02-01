#!/bin/bash -e

test_system_workflows()
{
    echo "### Testing rest-service with V2.1 client..."
    pushd workflows && tox && popd
}

test_rest_service_v3_endpoints()
{
    echo "### Testing rest-service endpoints with V3 client..."
    pushd rest-service && tox -e clientV3-endpoints && popd
}

test_rest_service_v3_infrastructure()
{
    echo "### Testing rest-service infrastructure with V3 client..."
    pushd rest-service && tox -e clientV3-infrastructure && popd
}

test_rest_service_v2_1_endpoints()
{
    echo "### Testing rest-service endpoints with V2.1 client..."
    pushd rest-service && tox -e clientV2_1-endpoints && popd
}

test_rest_service_v2_1_infrastructure()
{
    echo "### Testing rest-service infrastructure with V2.1 client..."
    pushd rest-service && tox -e clientV2_1-infrastructure && popd
}

test_rest_service_v2_endpoints()
{
    echo "### Testing rest-service endpoints with V2 client..."
    pushd rest-service && tox -e clientV2-endpoints && popd
}

test_rest_service_v2_infrastructure()
{
    echo "### Testing rest-service infrastructure with V2 client..."
    pushd rest-service && tox -e clientV2-infrastructure && popd
}

test_rest_service_v1_endpoints()
{
    echo "### Testing rest-service endpoints V1 client..."
    pushd rest-service && tox -e clientV1-endpoints && popd
}

test_rest_service_v1_infrastructure()
{
    echo "### Testing rest-service infrastructure V1 client..."
    pushd rest-service && tox -e clientV1-infrastructure && popd
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
    test-rest-service-endpoints-v3-client           ) test_rest_service_v3_endpoints;;
    test-rest-service-infrastructure-v3-client      ) test_rest_service_v3_infrastructure;;
    test-rest-service-endpoints-v2_1-client         ) test_rest_service_v2_1_endpoints;;
    test-rest-service-infrastructure-v2_1-client    ) test_rest_service_v2_1_infrastructure;;
    test-rest-service-endpoints-v2-client           ) test_rest_service_v2_endpoints;;
    test-rest-service-infrastructure-v2-client      ) test_rest_service_v2_infrastructure;;
    test-rest-service-endpoints-v1-client           ) test_rest_service_v1_endpoints;;
    test-rest-service-infrastructure-v1-client      ) test_rest_service_v1_infrastructure;;
    flake8                                          ) run_flake8;;
    test-system-workflows                           ) test_system_workflows;;
esac
