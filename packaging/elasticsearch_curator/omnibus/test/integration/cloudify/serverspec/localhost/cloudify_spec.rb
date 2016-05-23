require 'spec_helper'

if ['centos', 'redhat'].include?(os[:family])

  describe file('/opt/es-curator/embedded') do
    it { should be_directory }
    it { should be_readable }
  end
end
