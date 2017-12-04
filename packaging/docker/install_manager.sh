#!/usr/bin/env bash

set -eu

IMAGE_PUB_NAME="docker_cfy_manager"

CONTAINER_IP=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${CONTAINER_NAME})

echo "Creating install config file..."
echo "manager:
  private_ip: ${CONTAINER_IP}
  public_ip: ${CONTAINER_IP}
  set_manager_ip_on_boot: true
  security:
    admin_password: admin" > config.yaml

docker cp config.yaml ${CONTAINER_NAME}:/opt/cloudify-manager-install/config.yaml

echo "Installing manager..."
docker exec -t ${CONTAINER_NAME} sh -c "cfy_manager install"
echo "The Manager's IP is ${CONTAINER_IP}"
