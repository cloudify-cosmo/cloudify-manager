
require 'rubygems'
require 'json'

puts `ruby -v`
puts `gem search json`

h = {}
p = h
(1..21).each do |i|
  p['a'] = {}
  p = p['a']
end

s = h.to_json

p s

h = JSON.parse(s, :max_nesting => 100)

p h

