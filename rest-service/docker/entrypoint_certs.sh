#!/usr/bin/env -S bash -eux

# this is a (temporary) script for creating all the certificates that
# the manager needs.
# eventually, this will need to be replaced by something more robust,
# especially wrt. the hardcoded subject names

if [ ! -e "/tmp/ca.config" ]; then
    echo "
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ext
[ req_distinguished_name ]
commonName = _common_name # ignored, _default is used instead
commonName_default = Cloudify generated certificate
[ v3_ext ]
basicConstraints=CA:true
subjectKeyIdentifier=hash
" > /tmp/ca.config
fi


if [ ! -e "/ssl/cloudify_internal_ca_cert.pem" ]; then
    openssl req \
        -x509 \
        -newkey rsa:4096 \
        -batch \
        -keyout /ssl/cloudify_internal_ca_key.pem \
        -out /ssl/cloudify_internal_ca_cert.pem \
        -sha256 \
        -nodes \
        -days 3650 \
        -config /tmp/ca.config
fi

if [ ! -e "/ssl/cloudify_external_cert.pem" ]; then
    openssl req \
        -newkey rsa:4096 \
        -nodes \
        -batch \
        -sha256 \
        -keyout /ssl/cloudify_external_key.pem \
        -out /ssl/cloudify_external_cert.req \
        -subj '/CN=nginx'

    openssl x509 \
        -CA /ssl/cloudify_internal_ca_cert.pem \
        -CAkey /ssl/cloudify_internal_ca_key.pem \
        -CAcreateserial \
        -sha256 \
        -req -in /ssl/cloudify_external_cert.req \
        -out /ssl/cloudify_external_cert.pem \
        -days 3650
fi

if [ ! -e "/ssl/cloudify_internal_cert.pem" ]; then
    openssl req \
        -newkey rsa:4096 \
        -nodes \
        -batch \
        -sha256 \
        -keyout /ssl/cloudify_internal_key.pem \
        -out /ssl/cloudify_internal_cert.req \
        -subj '/CN=nginx'

    openssl x509 \
        -CA /ssl/cloudify_internal_ca_cert.pem \
        -CAkey /ssl/cloudify_internal_ca_key.pem \
        -CAcreateserial \
        -sha256 \
        -req -in /ssl/cloudify_internal_cert.req \
        -out /ssl/cloudify_internal_cert.pem \
        -days 3650
fi

if [ ! -e "/ssl/rabbitmq-cert.pem" ]; then
    openssl req \
        -newkey rsa:4096 \
        -nodes \
        -batch \
        -sha256 \
        -keyout /ssl/rabbitmq-key.pem \
        -out /ssl/rabbitmq-cert.req \
        -subj '/CN=rabbitmq'

    openssl x509 \
        -CA /ssl/cloudify_internal_ca_cert.pem \
        -CAkey /ssl/cloudify_internal_ca_key.pem \
        -CAcreateserial \
        -sha256 \
        -req -in /ssl/rabbitmq-cert.req \
        -out /ssl/rabbitmq-cert.pem \
        -days 3650
fi

chmod -R a+r /ssl
