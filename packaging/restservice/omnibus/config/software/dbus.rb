name "dbus"

build do
  command ["#{install_dir}/embedded/bin/pip",
           "install", "--build=#{project_dir}/#{name}", "dbus-python"]
end