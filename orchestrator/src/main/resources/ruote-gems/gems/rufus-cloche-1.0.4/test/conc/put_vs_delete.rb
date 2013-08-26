
$:.unshift('lib')

require 'rufus-json/automatic'
require 'rufus-cloche'

workdir = File.join(File.dirname(__FILE__), '..', '..', 'tcloche')

FileUtils.rm_rf(workdir) rescue nil

C = Rufus::Cloche.new(:dir => workdir)

d = C.get('whatever', 'nada')
C.delete(d) if d

C.put({ '_id' => 'nada', 'where' => 'London', 'type' => 'whatever' })
$d = C.get('whatever', 'nada')

Thread.abort_on_exception = true

t1 = Thread.new do
  p [ Thread.current.object_id, :delete, $d['_rev'], C.delete($d) ]
end
t0 = Thread.new do
  p [ Thread.current.object_id, :put, $d['_rev'], C.put($d) ]
end

sleep 0.100

p C.get('whatever', 'nada')
p C.get('whatever', 'nada')

