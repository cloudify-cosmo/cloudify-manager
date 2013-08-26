# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "rufus-cloche"
  s.version = "1.0.4"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux"]
  s.date = "2013-02-21"
  s.description = "\nA very stupid JSON hash store.\n\nIt's built on top of yajl-ruby and File.lock. Defaults to 'json' (or 'json_pure') if yajl-ruby is not present (it's probably just a \"gem install yajl-ruby\" away.\n\nStrives to be process-safe and thread-safe.\n  "
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://ruote.rubyforge.org"
  s.require_paths = ["lib"]
  s.rubyforge_project = "rufus"
  s.rubygems_version = "1.8.24"
  s.summary = "an open source Ruby workflow engine"

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_runtime_dependency(%q<rufus-json>, [">= 1.0.3"])
      s.add_development_dependency(%q<rake>, [">= 0"])
      s.add_development_dependency(%q<json>, [">= 0"])
    else
      s.add_dependency(%q<rufus-json>, [">= 1.0.3"])
      s.add_dependency(%q<rake>, [">= 0"])
      s.add_dependency(%q<json>, [">= 0"])
    end
  else
    s.add_dependency(%q<rufus-json>, [">= 1.0.3"])
    s.add_dependency(%q<rake>, [">= 0"])
    s.add_dependency(%q<json>, [">= 0"])
  end
end
