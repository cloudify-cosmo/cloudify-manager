#! /usr/bin/env bash
set -e

function set_manager_ip() {

  ip=$(/usr/sbin/ip a s | /usr/bin/grep -oE 'inet [^/]+' | /usr/bin/cut -d' ' -f2 | /usr/bin/grep -v '^127.' | /usr/bin/grep -v '^169.254.' | /usr/bin/head -n1)

  echo "Setting manager IP to: ${ip}"

  echo "Updating cloudify-amqpinflux.."
  /usr/bin/sed -i -e "s/AMQP_HOST=.*/AMQP_HOST="'"'"${ip}"'"'"/" /etc/sysconfig/cloudify-amqpinflux

  echo "Updating cloudify-riemann.."
  /usr/bin/sed -i -e "s/RABBITMQ_HOST=.*/RABBITMQ_HOST="'"'"${ip}"'"'"/" /etc/sysconfig/cloudify-riemann
  /usr/bin/sed -i -e "s/REST_HOST=.*/REST_HOST="'"'"${ip}"'"'"/" /etc/sysconfig/cloudify-riemann

  echo "Updating cloudify-mgmtworker.."
  /usr/bin/sed -i -e "s/REST_HOST=.*/REST_HOST="'"'"${ip}"'"'"/" /etc/sysconfig/cloudify-mgmtworker
  /usr/bin/sed -i -e "s#MANAGER_FILE_SERVER_URL="'"'"https://.*:53333/resources"'"'"#MANAGER_FILE_SERVER_URL="'"'"https://${ip}:53333/resources"'"'"#" /etc/sysconfig/cloudify-mgmtworker

  echo "Updating cloudify-manager (rest-service).."
  /usr/bin/sed -i -e "s#amqp_host: '.*'#amqp_host: '${ip}'#" /opt/manager/cloudify-rest.conf
  /usr/bin/sed -i -e "s#file_server_url: 'https://[^:]*:\(.*\)#file_server_url: 'https://${ip}:\1#" /opt/manager/cloudify-rest.conf

  echo "Updating broker_config.json.."
  /usr/bin/sed -i -e "s/"'"'"broker_hostname"'"'": "'"'".*"'"'"/"'"'"broker_hostname"'"'": "'"'"${ip}"'"'"/" /opt/mgmtworker/work/broker_config.json

  echo "Updating broker_ip in provider context.."
  /opt/manager/env/bin/python /opt/cloudify/manager-ip-setter/update-provider-context.py ${ip}

  echo "Creating internal SSL certificates.."
  cfy_manager create-internal-certs --manager-ip ${ip}

  echo "Updating logstash config..."
  /usr/bin/sed -i -e 's/host => ".*"/host => "'"${ip}"'"/g' /etc/logstash/conf.d/logstash.conf
  
  echo "Done!"

}

touched_file_path="/opt/cloudify/manager-ip-setter/touched"

if [ ! -f ${touched_file_path} ]; then
  set_manager_ip
  touch ${touched_file_path}
else
  echo "${touched_file_path} exists - not setting manager ip."
fi
