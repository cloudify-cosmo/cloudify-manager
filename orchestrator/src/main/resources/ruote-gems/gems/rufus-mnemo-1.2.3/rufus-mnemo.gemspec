
Gem::Specification.new do |s|

  s.name = 'rufus-mnemo'

  s.version = File.read(
    File.expand_path('../lib/rufus/mnemo.rb', __FILE__)
  ).match(/ VERSION *= *['"]([^'"]+)/)[1]

  s.platform = Gem::Platform::RUBY
  s.authors = [ 'John Mettraux' ]
  s.email = %w[ jmettraux@gmail.com ]
  s.homepage = 'http://github.com/jmettraux/rufus-mnemo/'
  s.rubyforge_project = 'rufus'
  s.summary = 'Turning (large) integers into japanese sounding words and vice versa'
  s.description = %{
Turning (large) integers into japanese sounding words and vice versa
  }

  #s.files = `git ls-files`.split("\n")
  s.files = Dir[
    'Rakefile',
    'lib/**/*.rb', 'spec/**/*.rb', 'test/**/*.rb',
    '*.gemspec', '*.txt', '*.rdoc', '*.md', '*.mdown'
  ]

  #s.add_dependency 'rufus-json', '>= 1.0.1'

  s.add_development_dependency 'rake'

  s.require_path = 'lib'
end

