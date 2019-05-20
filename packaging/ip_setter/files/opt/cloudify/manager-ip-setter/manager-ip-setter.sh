#! /usr/bin/env bash
set -e

function set_manager_ip() {

  ip=$(/usr/sbin/ip a s | /usr/bin/grep -oE 'inet [^/]+' | /usr/bin/cut -d' ' -f2 | /usr/bin/grep -v '^127.' | /usr/bin/grep -v '^169.254.' | /usr/bin/head -n1)

  echo "Setting manager IP to: ${ip}"

  echo "Updating cloudify-mgmtworker.."
  /usr/bin/sed -i -e "s/REST_HOST=.*/REST_HOST="'"'"${ip}"'"'"/" /etc/sysconfig/cloudify-mgmtworker
  /usr/bin/sed -i -e "s#MANAGER_FILE_SERVER_URL="'"'"https://.*:53333/resources"'"'"#MANAGER_FILE_SERVER_URL="'"'"https://${ip}:53333/resources"'"'"#" /etc/sysconfig/cloudify-mgmtworker

  echo "Updating cloudify-manager (rest-service).."
  /usr/bin/sed -i -e "s#amqp_host: '.*'#amqp_host: '${ip}'#" /opt/manager/cloudify-rest.conf

  echo "Updating IPs stored in the database..."
  sudo -upostgres psql cloudify_db -c "update config set value=regexp_replace(value, 'https://[^:]+:(.*)', 'https://${ip}:\1', 'g') where name='file_server_url'"

  echo "Updating broker_ip in provider context.."
  /opt/manager/env/bin/python /opt/cloudify/manager-ip-setter/update-provider-context.py ${ip}

  echo "Updating networks in certificate metadata..."
  /usr/bin/sed -ri "s/"'"'"broker_addresses"'"'"[^]]+]/"'"'"broker_addresses"'"'": \\["'"'"${ip}"'"'"]/" /etc/cloudify/ssl/certificate_metadata
  /usr/bin/sed -ri "s/"'"'"manager_addresses"'"'"[^]]+]/"'"'"manager_addresses"'"'": \\["'"'"${ip}"'"'"]/" /etc/cloudify/ssl/certificate_metadata

  echo "Creating internal SSL certificates.."
  cfy_manager create-internal-certs --manager-hostname $(hostname -s)

  echo "Done!"

}

touched_file_path="/opt/cloudify/manager-ip-setter/touched"

if [ ! -f ${touched_file_path} ]; then
  set_manager_ip
  touch ${touched_file_path}
else
  echo "${touched_file_path} exists - not setting manager ip."
fi
