
#
# Specifying rufus-treechecker
#
# Wed Dec 22 17:06:17 JST 2010
#

require File.join(File.dirname(__FILE__), 'spec_base')


module Testy
  class Tasty
  end
end


describe Rufus::TreeChecker do

  context 'as a [complete] ruleset' do

    let :tc do

      Rufus::TreeChecker.new do

        exclude_fvccall :abort
        exclude_fvccall :exit, :exit!
        exclude_fvccall :system
        exclude_fvccall :at_exit
        exclude_eval
        exclude_alias
        exclude_global_vars
        exclude_call_on File, FileUtils
        exclude_class_tinkering :except => Testy::Tasty
        exclude_module_tinkering

        exclude_fvcall :public
        exclude_fvcall :protected
        exclude_fvcall :private
        exclude_fcall :load
        exclude_fcall :require
      end
    end

    [
      '1 + 1',
      'puts "toto"',
      "class Toto < Testy::Tasty\nend",
      "class Toto < Testy::Tasty; end"
    ].each do |code|

      it "doesn't block #{code.inspect}" do
        lambda { tc.check(code) }.should_not raise_error
      end
    end

    [
      "exit",
      "puts $BATEAU",
      "abort",
      "abort; puts 'ok'",
      "puts 'ok'; abort",

      "exit 0",
      "system('whatever')",

      "alias :a :b",
      "alias_method :a, :b",

      "File.open('x')",
      "FileUtils.rm('x')",

      "eval 'nada'",
      "M.module_eval 'nada'",
      "o.instance_eval 'nada'",

      "class String\nend",
      "module Whatever\nend",
      "class << e\nend",

      "class String; end",
      "module Whatever; end",
      "class << e; end",

      "at_exit { puts 'over.' }",
      "Kernel.at_exit { puts 'over.' }"
    ].each do |code|

      it "blocks #{code.inspect}" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end
end

