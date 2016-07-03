name "flask-securest"

default_version '0.8'

source :git => "https://github.com/cloudify-cosmo/flask-securest"

build do
  command ["#{install_dir}/embedded/bin/pip",
           "install", "--build=#{project_dir}/#{name}", "."]
end