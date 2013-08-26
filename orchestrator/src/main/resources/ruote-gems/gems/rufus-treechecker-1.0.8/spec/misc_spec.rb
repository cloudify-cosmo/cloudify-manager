
#
# Specifying rufus-treechecker
#
# Wed Dec 22 16:58:11 JST 2010
#

require File.join(File.dirname(__FILE__), 'spec_base')


describe Rufus::TreeChecker do

  describe '.parse' do

    it 'returns the AST as an array' do

      Rufus::TreeChecker.parse('1 + 1').should ==
        [ :call, [ :lit, 1 ], :+, [ :arglist, [ :lit, 1 ] ] ]
    end
  end

  describe '.clone' do

    it "returns a copy of the TreeChecker" do

      tc0 = Rufus::TreeChecker.new do
        exclude_fvccall :abort
      end

      tc1 = tc0.clone

      [ tc0, tc1 ].each do |tc|
        class << tc
          attr_reader :set, :root_set
        end
      end

      tc1.set.object_id.should_not == tc0.set.object_id
      tc1.root_set.object_id.should_not == tc0.root_set.object_id

      tc1.set.should == tc0.set
      tc1.root_set.should == tc0.root_set
    end

    it "sets @current_set correctly when cloning" do

      tc0 = Rufus::TreeChecker.new

      tc1 = tc0.clone

      tc1.add_rules do
        exclude_def
        exclude_raise
      end

      [ tc0, tc1 ].each do |tc|
        class << tc
          attr_reader :set, :root_set
        end
      end

      tc0.set.excluded_symbols.keys.should_not include(:defn)
      tc1.set.excluded_symbols.keys.should include(:defn)

      tc0.set.excluded_patterns.size.should == 0
      tc1.set.excluded_patterns.size.should == 3
    end

    it "does deep copy" do

      tc0 = Rufus::TreeChecker.new do

        exclude_fvccall :abort, :exit, :exit!
        exclude_fvccall :system, :fork, :syscall, :trap, :require, :load
        exclude_fvccall :at_exit

        exclude_fvcall :private, :public, :protected

        exclude_eval              # no eval, module_eval or instance_eval
        exclude_backquotes        # no `rm -fR the/kitchen/sink`
        exclude_alias             # no alias or aliast_method
        exclude_global_vars       # $vars are off limits
        exclude_module_tinkering  # no module opening

        exclude_rebinding Kernel # no 'k = Kernel'

        exclude_access_to(
          IO, File, FileUtils, Process, Signal, Thread, ThreadGroup)

        exclude_call_to :instance_variable_get, :instance_variable_set
      end

      tc1 = tc0.clone
      tc1.add_rules do
        exclude_def
      end

      tc2 = tc0.clone
      tc2.add_rules do
        exclude_raise
      end

      [ tc0, tc1, tc2 ].each do |tc|
        class << tc
          attr_reader :set, :root_set
        end
      end

      tc0.set.excluded_symbols.keys.size.should == 6
      tc1.set.excluded_symbols.keys.size.should == 7
      tc2.set.excluded_symbols.keys.size.should == 6

      tc0.set.excluded_patterns[:fcall].size.should == 13
      tc1.set.excluded_patterns[:fcall].size.should == 13
      tc2.set.excluded_patterns[:fcall].size.should == 15
    end
  end
end

