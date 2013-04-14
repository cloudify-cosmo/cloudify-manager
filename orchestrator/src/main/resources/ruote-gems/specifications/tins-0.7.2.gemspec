# -*- encoding: utf-8 -*-

Gem::Specification.new do |s|
  s.name = "tins"
  s.version = "0.7.2"

  s.required_rubygems_version = Gem::Requirement.new(">= 0") if s.respond_to? :required_rubygems_version=
  s.authors = ["Florian Frank"]
  s.date = "2013-03-10"
  s.description = "All the stuff that isn't good/big enough for a real library."
  s.email = "flori@ping.de"
  s.extra_rdoc_files = ["README.rdoc", "lib/spruz.rb", "lib/tins.rb", "lib/tins/alias.rb", "lib/tins/ask_and_send.rb", "lib/tins/attempt.rb", "lib/tins/bijection.rb", "lib/tins/concern.rb", "lib/tins/count_by.rb", "lib/tins/date_dummy.rb", "lib/tins/date_time_dummy.rb", "lib/tins/deep_const_get.rb", "lib/tins/deep_dup.rb", "lib/tins/extract_last_argument_options.rb", "lib/tins/file_binary.rb", "lib/tins/find.rb", "lib/tins/generator.rb", "lib/tins/go.rb", "lib/tins/hash_symbolize_keys_recursive.rb", "lib/tins/hash_union.rb", "lib/tins/if_predicate.rb", "lib/tins/limited.rb", "lib/tins/lines_file.rb", "lib/tins/memoize.rb", "lib/tins/minimize.rb", "lib/tins/module_group.rb", "lib/tins/named_set.rb", "lib/tins/null.rb", "lib/tins/once.rb", "lib/tins/p.rb", "lib/tins/partial_application.rb", "lib/tins/proc_compose.rb", "lib/tins/proc_prelude.rb", "lib/tins/range_plus.rb", "lib/tins/require_maybe.rb", "lib/tins/responding.rb", "lib/tins/rotate.rb", "lib/tins/round.rb", "lib/tins/secure_write.rb", "lib/tins/shuffle.rb", "lib/tins/string_camelize.rb", "lib/tins/string_underscore.rb", "lib/tins/string_version.rb", "lib/tins/subhash.rb", "lib/tins/time_dummy.rb", "lib/tins/to.rb", "lib/tins/to_proc.rb", "lib/tins/uniq_by.rb", "lib/tins/version.rb", "lib/tins/write.rb", "lib/tins/xt.rb", "lib/tins/xt/ask_and_send.rb", "lib/tins/xt/attempt.rb", "lib/tins/xt/blank.rb", "lib/tins/xt/count_by.rb", "lib/tins/xt/date_dummy.rb", "lib/tins/xt/date_time_dummy.rb", "lib/tins/xt/deep_const_get.rb", "lib/tins/xt/deep_dup.rb", "lib/tins/xt/extract_last_argument_options.rb", "lib/tins/xt/file_binary.rb", "lib/tins/xt/full.rb", "lib/tins/xt/hash_symbolize_keys_recursive.rb", "lib/tins/xt/hash_union.rb", "lib/tins/xt/if_predicate.rb", "lib/tins/xt/irb.rb", "lib/tins/xt/named.rb", "lib/tins/xt/null.rb", "lib/tins/xt/p.rb", "lib/tins/xt/partial_application.rb", "lib/tins/xt/proc_compose.rb", "lib/tins/xt/proc_prelude.rb", "lib/tins/xt/range_plus.rb", "lib/tins/xt/require_maybe.rb", "lib/tins/xt/responding.rb", "lib/tins/xt/rotate.rb", "lib/tins/xt/round.rb", "lib/tins/xt/secure_write.rb", "lib/tins/xt/shuffle.rb", "lib/tins/xt/string.rb", "lib/tins/xt/string_camelize.rb", "lib/tins/xt/string_underscore.rb", "lib/tins/xt/string_version.rb", "lib/tins/xt/subhash.rb", "lib/tins/xt/symbol_to_proc.rb", "lib/tins/xt/time_dummy.rb", "lib/tins/xt/to.rb", "lib/tins/xt/uniq_by.rb", "lib/tins/xt/write.rb"]
  s.files = ["README.rdoc", "lib/spruz.rb", "lib/tins.rb", "lib/tins/alias.rb", "lib/tins/ask_and_send.rb", "lib/tins/attempt.rb", "lib/tins/bijection.rb", "lib/tins/concern.rb", "lib/tins/count_by.rb", "lib/tins/date_dummy.rb", "lib/tins/date_time_dummy.rb", "lib/tins/deep_const_get.rb", "lib/tins/deep_dup.rb", "lib/tins/extract_last_argument_options.rb", "lib/tins/file_binary.rb", "lib/tins/find.rb", "lib/tins/generator.rb", "lib/tins/go.rb", "lib/tins/hash_symbolize_keys_recursive.rb", "lib/tins/hash_union.rb", "lib/tins/if_predicate.rb", "lib/tins/limited.rb", "lib/tins/lines_file.rb", "lib/tins/memoize.rb", "lib/tins/minimize.rb", "lib/tins/module_group.rb", "lib/tins/named_set.rb", "lib/tins/null.rb", "lib/tins/once.rb", "lib/tins/p.rb", "lib/tins/partial_application.rb", "lib/tins/proc_compose.rb", "lib/tins/proc_prelude.rb", "lib/tins/range_plus.rb", "lib/tins/require_maybe.rb", "lib/tins/responding.rb", "lib/tins/rotate.rb", "lib/tins/round.rb", "lib/tins/secure_write.rb", "lib/tins/shuffle.rb", "lib/tins/string_camelize.rb", "lib/tins/string_underscore.rb", "lib/tins/string_version.rb", "lib/tins/subhash.rb", "lib/tins/time_dummy.rb", "lib/tins/to.rb", "lib/tins/to_proc.rb", "lib/tins/uniq_by.rb", "lib/tins/version.rb", "lib/tins/write.rb", "lib/tins/xt.rb", "lib/tins/xt/ask_and_send.rb", "lib/tins/xt/attempt.rb", "lib/tins/xt/blank.rb", "lib/tins/xt/count_by.rb", "lib/tins/xt/date_dummy.rb", "lib/tins/xt/date_time_dummy.rb", "lib/tins/xt/deep_const_get.rb", "lib/tins/xt/deep_dup.rb", "lib/tins/xt/extract_last_argument_options.rb", "lib/tins/xt/file_binary.rb", "lib/tins/xt/full.rb", "lib/tins/xt/hash_symbolize_keys_recursive.rb", "lib/tins/xt/hash_union.rb", "lib/tins/xt/if_predicate.rb", "lib/tins/xt/irb.rb", "lib/tins/xt/named.rb", "lib/tins/xt/null.rb", "lib/tins/xt/p.rb", "lib/tins/xt/partial_application.rb", "lib/tins/xt/proc_compose.rb", "lib/tins/xt/proc_prelude.rb", "lib/tins/xt/range_plus.rb", "lib/tins/xt/require_maybe.rb", "lib/tins/xt/responding.rb", "lib/tins/xt/rotate.rb", "lib/tins/xt/round.rb", "lib/tins/xt/secure_write.rb", "lib/tins/xt/shuffle.rb", "lib/tins/xt/string.rb", "lib/tins/xt/string_camelize.rb", "lib/tins/xt/string_underscore.rb", "lib/tins/xt/string_version.rb", "lib/tins/xt/subhash.rb", "lib/tins/xt/symbol_to_proc.rb", "lib/tins/xt/time_dummy.rb", "lib/tins/xt/to.rb", "lib/tins/xt/uniq_by.rb", "lib/tins/xt/write.rb"]
  s.homepage = "http://flori.github.com/tins"
  s.rdoc_options = ["--title", "Tins - Useful stuff.", "--main", "README.rdoc"]
  s.require_paths = ["lib"]
  s.rubygems_version = "1.8.24"
  s.summary = "Useful stuff."

  if s.respond_to? :specification_version then
    s.specification_version = 4

    if Gem::Version.new(Gem::VERSION) >= Gem::Version.new('1.2.0') then
      s.add_development_dependency(%q<gem_hadar>, ["~> 0.1.8"])
      s.add_development_dependency(%q<test-unit>, ["~> 2.5"])
      s.add_development_dependency(%q<utils>, [">= 0"])
    else
      s.add_dependency(%q<gem_hadar>, ["~> 0.1.8"])
      s.add_dependency(%q<test-unit>, ["~> 2.5"])
      s.add_dependency(%q<utils>, [">= 0"])
    end
  else
    s.add_dependency(%q<gem_hadar>, ["~> 0.1.8"])
    s.add_dependency(%q<test-unit>, ["~> 2.5"])
    s.add_dependency(%q<utils>, [">= 0"])
  end
end
