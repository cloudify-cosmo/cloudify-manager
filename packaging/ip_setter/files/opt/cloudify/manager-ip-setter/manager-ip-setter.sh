#! /usr/bin/env bash
set -e

function set_manager_ip() {

  ip=$(/usr/sbin/ip a s | /usr/bin/grep -oE 'inet [^/]+' | /usr/bin/cut -d' ' -f2 | /usr/bin/grep -v '^127.' | /usr/bin/grep -v '^169.254.' | /usr/bin/head -n1)

  echo "Setting manager IP to: ${ip}"

  echo "Updating cloudify-mgmtworker..."
  mgtworker_config="/etc/sysconfig/cloudify-mgmtworker"
  if [ ! -f "$mgtworker_config" ]; then
      mgtworker_config="/etc/supervisord.d/rabbitmq.cloudify.conf"
  fi

  /usr/bin/sed -i -e "s/REST_HOST=.*/REST_HOST="'"'"${ip}"'"'"/" $mgtworker_config
  /usr/bin/sed -i -e "s#MANAGER_FILE_SERVER_URL="'"'"https://.*:53333/resources"'"'"#MANAGER_FILE_SERVER_URL="'"'"https://${ip}:53333/resources"'"'"#" $mgtworker_config

  echo "Updating cloudify-manager (rest-service)..."
  /usr/bin/sed -i -e "s#amqp_host: '.*'#amqp_host: '${ip}'#" /opt/manager/cloudify-rest.conf

  echo "Updating IPs stored in the database..."
  sudo -upostgres psql cloudify_db -c "update config set value=regexp_replace(value, 'https://[^:]+:(.*)', 'https://${ip}:\1', 'g') where name='file_server_url'"

  echo "Updating the ip of the manager, broker and db-node in db..."
  /opt/manager/env/bin/python /opt/cloudify/manager-ip-setter/update-db.py ${ip}

  echo "Updating networks in certificate metadata..."
  /usr/bin/sed -ri "s/"'"'"broker_addresses"'"'"[^]]+]/"'"'"broker_addresses"'"'": \\["'"'"${ip}"'"'"]/" /etc/cloudify/ssl/certificate_metadata
  /usr/bin/sed -ri "s/"'"'"manager_addresses"'"'"[^]]+]/"'"'"manager_addresses"'"'": \\["'"'"${ip}"'"'"]/" /etc/cloudify/ssl/certificate_metadata

  echo "Creating internal SSL certificates..."
  cfy_manager create-internal-certs --manager-hostname cloudify

  echo "Updating monitoring certificates..."
  for cert_type in cert key; do
    cp /etc/cloudify/ssl/cloudify_internal_${cert_type}.pem /etc/cloudify/ssl/monitoring_${cert_type}.pem
  done

  echo "Done!"
}


function set_manager_ip_supervisord() {

  # Stop required services
  /usr/bin/supervisorctl -c /etc/supervisord.conf stop \
                          cloudify-mgmtworker \
                          cloudify-restservice \
                          cloudify-stage \
                          nginx \
                          cloudify-rabbitmq \
                          cloudify-amqp-postgres


  set_manager_ip

  echo "Update services"
  /usr/bin/supervisorctl -c /etc/supervisord.conf reread

  echo "Starting All services"
  /usr/bin/supervisorctl -c /etc/supervisord.conf restart \
                          cloudify-restservice \
                          cloudify-stage \
                          nginx \
                          cloudify-rabbitmq \
                          cloudify-amqp-postgres \
                          cloudify-mgmtworker

}


function set_prometheus_ip() {
  prometheus_yml="/etc/prometheus/prometheus.yml"
  if [ ! -f ${prometheus_yml} ]; then
    return
  fi

  echo "Updating the host label in the Prometheus local targets..."
  prometheus_targets="/etc/prometheus/targets/local_*.yml"
  for target_file in ${prometheus_targets} ; do
    /usr/bin/sed -ri "s/^(\s+labels:.+\"?host\"?:.*)127\.0\.0\.1(.*)$/\1${ip}\2/" "${target_file}"
  done

  echo "Updating the host labels in the Prometheus alerts..."
  prometheus_alerts="/etc/prometheus/alerts/*_missing.yml"
  for alert_file in ${prometheus_alerts} ; do
      /usr/bin/sed -ri "s/host=\"127\.0\.0\.1\"/host=\"${ip}\"/" "${target_file}"
      /usr/bin/sed -ri "s/on node 127\.0\.0\.1/on node ${ip}/" "${target_file}"
  done
}


touched_file_path="/opt/cloudify/manager-ip-setter/touched"

if [ ! -f ${touched_file_path} ]; then
    if  grep -E 'service_management:\s+supervisord' /etc/cloudify/config.yaml; then
        set_manager_ip_supervisord
        set_prometheus_ip supervisord
    else
        set_manager_ip
        set_prometheus_ip
    fi
    touch ${touched_file_path}
else
  echo "${touched_file_path} exists - not setting manager ip."
fi
