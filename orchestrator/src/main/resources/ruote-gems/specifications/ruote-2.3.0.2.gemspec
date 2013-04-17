# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "ruote"
  s.version = "2.3.0.2"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["John Mettraux", "Kenneth Kalmer", "Torsten Schoenebaum"]
  s.date = "2013-01-10"
  s.description = "\nruote is an open source Ruby workflow engine\n  "
  s.email = ["jmettraux@gmail.com"]
  s.homepage = "http://ruote.rubyforge.org"
  s.require_paths = ["lib"]
  s.rubyforge_project = "ruote"
  s.rubygems_version = "1.8.24"
  s.summary = "an open source Ruby workflow engine"

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_runtime_dependency(%q<ruby_parser>, ["~> 2.3"])
      s.add_runtime_dependency(%q<blankslate>, ["= 2.1.2.4"])
      s.add_runtime_dependency(%q<parslet>, ["= 1.4.0"])
      s.add_runtime_dependency(%q<sourcify>, ["= 0.5.0"])
      s.add_runtime_dependency(%q<rufus-json>, [">= 1.0.1"])
      s.add_runtime_dependency(%q<rufus-cloche>, [">= 1.0.2"])
      s.add_runtime_dependency(%q<rufus-dollar>, [">= 1.0.4"])
      s.add_runtime_dependency(%q<rufus-mnemo>, [">= 1.2.2"])
      s.add_runtime_dependency(%q<rufus-scheduler>, [">= 2.0.16"])
      s.add_runtime_dependency(%q<rufus-treechecker>, [">= 1.0.8"])
      s.add_development_dependency(%q<rake>, [">= 0"])
      s.add_development_dependency(%q<json>, [">= 0"])
      s.add_development_dependency(%q<mailtrap>, [">= 0"])
    else
      s.add_dependency(%q<ruby_parser>, ["~> 2.3"])
      s.add_dependency(%q<blankslate>, ["= 2.1.2.4"])
      s.add_dependency(%q<parslet>, ["= 1.4.0"])
      s.add_dependency(%q<sourcify>, ["= 0.5.0"])
      s.add_dependency(%q<rufus-json>, [">= 1.0.1"])
      s.add_dependency(%q<rufus-cloche>, [">= 1.0.2"])
      s.add_dependency(%q<rufus-dollar>, [">= 1.0.4"])
      s.add_dependency(%q<rufus-mnemo>, [">= 1.2.2"])
      s.add_dependency(%q<rufus-scheduler>, [">= 2.0.16"])
      s.add_dependency(%q<rufus-treechecker>, [">= 1.0.8"])
      s.add_dependency(%q<rake>, [">= 0"])
      s.add_dependency(%q<json>, [">= 0"])
      s.add_dependency(%q<mailtrap>, [">= 0"])
    end
  else
    s.add_dependency(%q<ruby_parser>, ["~> 2.3"])
    s.add_dependency(%q<blankslate>, ["= 2.1.2.4"])
    s.add_dependency(%q<parslet>, ["= 1.4.0"])
    s.add_dependency(%q<sourcify>, ["= 0.5.0"])
    s.add_dependency(%q<rufus-json>, [">= 1.0.1"])
    s.add_dependency(%q<rufus-cloche>, [">= 1.0.2"])
    s.add_dependency(%q<rufus-dollar>, [">= 1.0.4"])
    s.add_dependency(%q<rufus-mnemo>, [">= 1.2.2"])
    s.add_dependency(%q<rufus-scheduler>, [">= 2.0.16"])
    s.add_dependency(%q<rufus-treechecker>, [">= 1.0.8"])
    s.add_dependency(%q<rake>, [">= 0"])
    s.add_dependency(%q<json>, [">= 0"])
    s.add_dependency(%q<mailtrap>, [">= 0"])
  end
end
