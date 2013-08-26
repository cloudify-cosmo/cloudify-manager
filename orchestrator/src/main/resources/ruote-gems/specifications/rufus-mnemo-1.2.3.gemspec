# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "rufus-mnemo"
  s.version = "1.2.3"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux"]
  s.date = "2012-06-16"
  s.description = "\nTurning (large) integers into japanese sounding words and vice versa\n  "
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://github.com/jmettraux/rufus-mnemo/"
  s.require_paths = ["lib"]
  s.rubyforge_project = "rufus"
  s.rubygems_version = "1.8.24"
  s.summary = "Turning (large) integers into japanese sounding words and vice versa"

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
