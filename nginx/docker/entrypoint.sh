#!/usr/bin/env bash
export DOLLAR='$'
envsubst <nginx/config/nginx.conf.template >/etc/nginx/nginx.conf

for file_path in nginx/config/conf.d/*.template; do
  file_name=${file_path##*/}
  file_base=${file_name%.template}

  envsubst <"$file_path" >/etc/nginx/conf.d/"$file_base"
done
nginx -g "daemon off;"
