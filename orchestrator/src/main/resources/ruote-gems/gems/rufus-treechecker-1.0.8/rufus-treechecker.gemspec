# encoding: utf-8

Gem::Specification.new do |s|

  s.name = 'rufus-treechecker'
  s.version = File.read('lib/rufus/treechecker.rb').match(/VERSION = '([^']+)'/)[1]
  s.platform = Gem::Platform::RUBY
  s.authors = [ 'John Mettraux' ]
  s.email = [ 'jmettraux@gmail.com' ]
  s.homepage = 'http://rufus.rubyforge.org'
  s.rubyforge_project = 'rufus'
  s.summary = "tests strings of Ruby code for unauthorized patterns (exit, eval, ...)"
  s.description = %{
    tests strings of Ruby code for unauthorized patterns (exit, eval, ...)
  }

  #s.files = `git ls-files`.split("\n")
  s.files = Dir[
    'Rakefile',
    'lib/**/*.rb', 'spec/**/*.rb', 'test/**/*.rb',
    '*.gemspec', '*.txt', '*.rdoc', '*.md'
  ]

  s.add_runtime_dependency 'ruby_parser', '>= 2.0.5'

  s.add_development_dependency 'rake'
  s.add_development_dependency 'rspec', '>= 2.0'

  s.require_path = 'lib'
end

