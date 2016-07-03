name "script-plugin"

default_version "1.4"

source :git => "https://github.com/cloudify-cosmo/cloudify-script-plugin"

build do
  command ["#{install_dir}/embedded/bin/pip",
           "install", "--build=#{project_dir}/#{name}", "."]
end