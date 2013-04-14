
Gem::Specification.new do |s|

  s.name = 'rufus-json'

  s.version = File.read(
    File.expand_path('../lib/rufus/json.rb', __FILE__)
  ).match(/ VERSION *= *['"]([^'"]+)/)[1]

  s.platform = Gem::Platform::RUBY
  s.authors = [ 'John Mettraux', 'Torsten Schoenebaum' ]
  s.email = [ 'jmettraux@gmail.com' ]
  s.homepage = 'http://github.com/jmettraux/rufus-json'
  s.rubyforge_project = 'rufus'
  s.summary = 'One interface to various JSON ruby libs, with a preference for yajl.'

  s.description = %{
One interface to various JSON ruby libs (yajl, oj, json, json_pure, json-jruby, active_support). Has a preference for yajl.
  }.strip

  #s.files = `git ls-files`.split("\n")
  s.files = Dir[
    'Rakefile',
    'lib/**/*.rb', 'spec/**/*.rb', 'test/**/*.rb',
    '*.gemspec', '*.txt', '*.rdoc', '*.md'
  ]

  #s.add_development_dependency 'oj'
  #s.add_development_dependency 'json'
  #s.add_development_dependency 'json_pure'
  #s.add_development_dependency 'yajl-ruby'
  #s.add_development_dependency 'activesupport'
  s.add_development_dependency 'rake'

  s.require_path = 'lib'
end

