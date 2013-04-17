# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "sourcify"
  s.version = "0.5.0"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["NgTzeYang"]
  s.date = "2011-05-01"
  s.description = ""
  s.email = ["ngty77@gmail.com"]
  s.extra_rdoc_files = ["README.rdoc"]
  s.files = ["README.rdoc"]
  s.homepage = "http://github.com/ngty/sourcify"
  s.require_paths = ["lib"]
  s.rubygems_version = "1.8.24"
  s.summary = "Workarounds before ruby-core officially supports Proc#to_source (& friends)"

  if s.respond_to? :specification_version then
    s.specification_version = 3

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_runtime_dependency(%q<ruby2ruby>, [">= 1.2.5"])
      s.add_runtime_dependency(%q<sexp_processor>, [">= 3.0.5"])
      s.add_runtime_dependency(%q<ruby_parser>, [">= 2.0.5"])
      s.add_runtime_dependency(%q<file-tail>, [">= 1.0.5"])
      s.add_development_dependency(%q<bacon>, [">= 0"])
    else
      s.add_dependency(%q<ruby2ruby>, [">= 1.2.5"])
      s.add_dependency(%q<sexp_processor>, [">= 3.0.5"])
      s.add_dependency(%q<ruby_parser>, [">= 2.0.5"])
      s.add_dependency(%q<file-tail>, [">= 1.0.5"])
      s.add_dependency(%q<bacon>, [">= 0"])
    end
  else
    s.add_dependency(%q<ruby2ruby>, [">= 1.2.5"])
    s.add_dependency(%q<sexp_processor>, [">= 3.0.5"])
    s.add_dependency(%q<ruby_parser>, [">= 2.0.5"])
    s.add_dependency(%q<file-tail>, [">= 1.0.5"])
    s.add_dependency(%q<bacon>, [">= 0"])
  end
end
