
$:.unshift(File.expand_path('../../lib', __FILE__))

require 'rufus-json/automatic'
require 'rufus-cloche'

CLO = Rufus::Cloche.new(:dir => 'cloche')

p $$

def process (task)
  puts "#{$$} . processing task #{task['_id']}"
  r = CLO.delete(task)
  if r
    puts "#{$$} x could not process task #{task['_id']}  ===================="
  else
    icon = task['_id'].match(/^#{$$}:/) ? 'o' : 'O'
    puts "#{$$} #{icon} processed task #{task['_id']}"
  end
end

loop do

  CLO.get_many('task').each { |task| process(task) }

  (rand * 12).to_i.times do |i|
    nt = {
      '_id' => "#{$$}:#{i}:#{(Time.now.to_f * 1000).to_i}",
      'type' => 'task'
    }
    t = CLO.put(nt)
    if t
      puts "#{$$} x new task #{nt['_id']} (failed)"
    else
      puts "#{$$} . new task #{nt['_id']}"
    end
  end
end

