
# reload ohai data
ohai 'reload' do
  action :reload
end

# should only be one of each rpm/deb
pkg_path = Dir.glob("#{node['etc']['passwd']['vagrant']['dir']}/cloudify/pkg/cloudify*rpm")[0] if node['platform_family'] == 'rhel'

package 'cloudify-amqp-influxdb' do
  action :install
  source pkg_path
end
