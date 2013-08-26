
$:.unshift(File.expand_path(File.join(File.dirname(__FILE__), '..', 'lib')))

require 'rufus-dollar'


#
# rspec helpers

Dir[File.join(File.dirname(__FILE__), 'support/*.rb')].each { |f| require(f) }

RSpec.configure do |config|
  config.include DollarHelper
end

