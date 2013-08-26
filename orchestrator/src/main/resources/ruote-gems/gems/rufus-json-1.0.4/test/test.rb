
#
# testing rufus-json
#
# Sat Jul 17 14:38:44 JST 2010
#

#R = `which ruby`.strip
R = 'bundle exec ruby'
P = File.dirname(__FILE__)
$result = ''

def do_test(command)

  puts
  puts '-' * 80
  puts command
  puts `#{command}`

  $result << ($?.exitstatus == 0 ? 'o' : 'X')
end

LIBS = %w[ json active_support json/pure ]
LIBS.concat %w[ yajl oj ] if RUBY_PLATFORM != 'java'

LIBS.each do |lib|
  do_test "export JSON=#{lib}; #{R} #{P}/do_test.rb"
end

do_test "#{R} #{P}/backend_test.rb"

puts
puts
puts '-' * 80
puts $result
puts '-' * 80
puts

