#!/bin/bash -e

install_dependencies() {
    echo "### Installing dependencies..."
    case $CIRCLE_NODE_INDEX in
        0)
            tox -c ./rest-service/tox.ini -e clientV1-endpoints --notest
            tox -c ./rest-service/tox.ini -e clientV1-infrastructure --notest
            ;;
        1)
            tox -c ./rest-service/tox.ini -e clientV2-endpoints --notest
            pip install flake8
            ;;
        2)
            tox -c ./rest-service/tox.ini -e clientV2-infrastructure --notest
            tox -c ./workflows/tox.ini --notest
            ;;
        3)
            tox -c ./rest-service/tox.ini -e clientV2_1-endpoints --notest
            ;;
        4)
            tox -c ./rest-service/tox.ini -e clientV2_1-infrastructure --notest
            ;;
        5)
            tox -c ./rest-service/tox.ini -e clientV3-endpoints --notest
            ;;
        6)
            tox -c ./rest-service/tox.ini -e clientV3-infrastructure --notest
            ;;
    esac
}

run() {
    echo "### Running tests..."
    case $CIRCLE_NODE_INDEX in
        0)
            tox -c ./rest-service/tox.ini -e clientV1-endpoints
            tox -c ./rest-service/tox.ini -e clientV1-infrastructure
            ;;
        1)
            tox -c ./rest-service/tox.ini -e clientV2-endpoints
            flake8 plugins/riemann-controller/ workflows/ rest-service/ tests/
            ;;
        2)
            tox -c ./rest-service/tox.ini -e clientV2-infrastructure
            tox -c ./workflows/tox.ini
            ;;
        3)
            tox -c ./rest-service/tox.ini -e clientV2_1-endpoints
            ;;
        4)
            tox -c ./rest-service/tox.ini -e clientV2_1-infrastructure
            ;;
        5)
            tox -c ./rest-service/tox.ini -e clientV3-endpoints
            ;;
        6)
            tox -c ./rest-service/tox.ini -e clientV3-infrastructure
            ;;
    esac
}

case $1 in
    --install-dependencies)
        install_dependencies
        ;;
    *)
        run
        ;;
esac
