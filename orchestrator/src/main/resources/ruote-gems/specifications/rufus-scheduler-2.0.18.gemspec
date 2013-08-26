# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "rufus-scheduler"
  s.version = "2.0.18"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux"]
  s.date = "2013-03-05"
  s.description = "job scheduler for Ruby (at, cron, in and every jobs)."
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://github.com/jmettraux/rufus-scheduler"
  s.require_paths = ["lib"]
  s.rubyforge_project = "rufus"
  s.rubygems_version = "1.8.24"
  s.summary = "job scheduler for Ruby (at, cron, in and every jobs)"

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_runtime_dependency(%q<tzinfo>, [">= 0.3.23"])
      s.add_development_dependency(%q<rake>, [">= 0"])
      s.add_development_dependency(%q<rspec>, [">= 2.7.0"])
    else
      s.add_dependency(%q<tzinfo>, [">= 0.3.23"])
      s.add_dependency(%q<rake>, [">= 0"])
      s.add_dependency(%q<rspec>, [">= 2.7.0"])
    end
  else
    s.add_dependency(%q<tzinfo>, [">= 0.3.23"])
    s.add_dependency(%q<rake>, [">= 0"])
    s.add_dependency(%q<rspec>, [">= 2.7.0"])
  end
end
