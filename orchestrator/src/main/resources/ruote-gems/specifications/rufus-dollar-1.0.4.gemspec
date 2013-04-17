# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "rufus-dollar"
  s.version = "1.0.4"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux"]
  s.date = "2010-12-23"
  s.description = "\n${xxx} substitutions\n  "
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://rufus.rubyforge.org"
  s.require_paths = ["lib"]
  s.rubyforge_project = "rufus"
  s.rubygems_version = "1.8.24"
  s.summary = "${xxx} substitutions"

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_development_dependency(%q<rake>, [">= 0"])
      s.add_development_dependency(%q<rspec>, [">= 2.0"])
    else
      s.add_dependency(%q<rake>, [">= 0"])
      s.add_dependency(%q<rspec>, [">= 2.0"])
    end
  else
    s.add_dependency(%q<rake>, [">= 0"])
    s.add_dependency(%q<rspec>, [">= 2.0"])
  end
end
