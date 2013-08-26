
require 'rubygems'

require 'benchmark'
include Benchmark

require 'rufus/treechecker'

Benchmark.benchmark do |b|

  tc = nil

  b.report do
    tc = Rufus::TreeChecker.new do

      exclude_fvccall :abort, :exit, :exit!
      exclude_fvccall :system, :fork, :syscall, :trap, :require, :load

      #exclude_call_to :class
      exclude_fvcall :private, :public, :protected

      #exclude_def               # no method definition
      exclude_eval              # no eval, module_eval or instance_eval
      exclude_backquotes        # no `rm -fR the/kitchen/sink`
      exclude_alias             # no alias or aliast_method
      exclude_global_vars       # $vars are off limits
      exclude_module_tinkering  # no module opening
      exclude_raise             # no raise or throw

      exclude_rebinding Kernel # no 'k = Kernel'

      exclude_access_to(
        IO, File, FileUtils, Process, Signal, Thread, ThreadGroup)

      #exclude_class_tinkering :except => OpenWFE::ProcessDefinition
      exclude_class_tinkering :except => Rufus::TreeChecker
        #
        # excludes defining/opening any class except
        # OpenWFE::ProcessDefinition

      exclude_call_to :instance_variable_get, :instance_variable_set
    end
  end

  DEF0 = <<-EOS
    #class MyDef0 < OpenWFE::ProcessDefinition
    class MyDef0 < Rufus::TreeChecker
      sequence do
        participant "alpha"
        participant 'alpha'
        alpha
      end
    end
  EOS

  N = 100
  #N = 1

  b.report do
    N.times { tc.check(DEF0) }
  end
end

#
# before RuleSet (N=100)
#
# mettraux:rufus-treechecker[master]/$ date
#   Tue Sep  2 09:33:06 JST 2008
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.000000   0.000000   0.000000 (  0.004252)
#   5.680000   0.040000   5.720000 (  5.745755)
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.010000   0.000000   0.010000 (  0.004367)
#   5.670000   0.040000   5.710000 (  5.731221)
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.010000   0.000000   0.010000 (  0.004247)
#   5.670000   0.040000   5.710000 (  5.727363)
#

#
# with RuleSet (N=100)
#
# mettraux:rufus-treechecker[master]/$ date
#   Tue Sep  2 13:25:24 JST 2008
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.000000   0.000000   0.000000 (  0.006439)
#   0.340000   0.000000   0.340000 (  0.342302)
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.000000   0.000000   0.000000 (  0.006269)
#   0.340000   0.000000   0.340000 (  0.342301)
# mettraux:rufus-treechecker[master]/$ ruby -Ilib test/bm.rb
#   0.000000   0.000000   0.000000 (  0.006350)
#   0.340000   0.000000   0.340000 (  0.342841)
#

