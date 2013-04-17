# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "rufus-json"
  s.version = "1.0.4"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux", "Torsten Schoenebaum"]
  s.date = "2013-03-06"
  s.description = "One interface to various JSON ruby libs (yajl, oj, json, json_pure, json-jruby, active_support). Has a preference for yajl."
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://github.com/jmettraux/rufus-json"
  s.require_paths = ["lib"]
  s.rubyforge_project = "rufus"
  s.rubygems_version = "1.8.24"
  s.summary = "One interface to various JSON ruby libs, with a preference for yajl."

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_development_dependency(%q<rake>, [">= 0"])
    else
      s.add_dependency(%q<rake>, [">= 0"])
    end
  else
    s.add_dependency(%q<rake>, [">= 0"])
  end
end
