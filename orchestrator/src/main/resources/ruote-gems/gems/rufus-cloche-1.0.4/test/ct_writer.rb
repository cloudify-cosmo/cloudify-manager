
$:.unshift(File.expand_path('../../lib', __FILE__))

require 'rufus-json/automatic'
require 'rufus-cloche'

CLO = Rufus::Cloche.new(:dir => 'cloche')
if doc = CLO.get('person', 'john')
  CLO.delete(doc)
end
CLO.put('type' => 'person', '_id' => 'john')

p $$

100.times do
  doc = CLO.get('person', 'john')
  sleep rand
  doc['pid'] = $$.to_s
  d = CLO.put(doc)
  puts d ? '* failure' : '. success'
  if d
    d['pid'] = $$.to_s
    d = CLO.put(d)
    puts d ? '    re_failure' : '    re_success'
  end
end

