
$:.unshift('lib')
require 'benchmark'
require 'rubygems'
require 'yajl'
require 'rufus/cloche'

N = 250

DOC = { '_id' => '0', 'type' => 'benchmark' }
1000.times { |i| DOC["key#{i}"] = { 'a' => 'b', 'c' => 'd', 'e' =>'f' } }

CLO = Rufus::Cloche.new(:dir => 'bm_cloche')

Benchmark.benchmark(' ' * 31 + Benchmark::Tms::CAPTION, 31) do |b|

  b.report('marshal to file') do
    N.times do
      File.open('out.marshal', 'wb') { |f| f.write(Marshal.dump(DOC)) }
    end
  end
  b.report('yajl to file') do
    N.times do
      File.open('out.json', 'wb') { |f| f.write(Yajl::Encoder.encode(DOC)) }
    end
  end
  b.report('to cloche') do
    N.times do |i|
      DOC['_id'] = i.to_s
      DOC['_rev'] = -1
      CLO.put(DOC)
    end
  end

  puts

  b.report('marshal from file') do
    N.times do
      doc = Marshal.load(File.read('out.marshal'))
    end
  end
  b.report('yajl from file') do
    N.times do
      doc = Yajl::Parser.parse(File.read('out.json'))
    end
  end
  b.report('from cloche') do
    N.times do |i|
      doc = CLO.get('benchmark', i.to_s)
    end
  end

  #puts
  #require 'json'
  #b.report('json to file') do
  #  N.times do
  #    File.open('out.json', 'wb') { |f| f.write(DOC.to_json) }
  #  end
  #end
  #b.report('json from file') do
  #  N.times do
  #    doc = ::JSON.parse(File.read('out.json'))
  #  end
  #end
end

