#--
# Copyright (c) 2008-2011, John Mettraux, jmettraux@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# "made in Japan" (as opposed to "swiss made")
#++


require 'ruby_parser'


module Rufus

  #
  # Instances of this error class are thrown when the ruby code being
  # checked contains exclude stuff
  #
  class SecurityError < RuntimeError
  end

  #
  # TreeChecker relies on ruby_parser to turns a piece of ruby code (a string)
  # into a bunch of sexpression and then TreeChecker will check that
  # sexpression tree and raise a Rufus::SecurityException if an excluded
  # pattern is spotted.
  #
  # The TreeChecker is meant to be useful for people writing DSLs directly
  # in Ruby (not via their own parser) that want to check and prevent
  # bad things from happening in this code.
  #
  #   tc = Rufus::TreeChecker.new do
  #     exclude_fvcall :abort
  #     exclude_fvcall :exit, :exit!
  #   end
  #
  #   tc.check("1 + 1; abort")               # will raise a SecurityError
  #   tc.check("puts (1..10).to_a.inspect")  # OK
  #
  #
  # == featured exclusion methods
  #
  # === call / vcall / fcall ?
  #
  # What the difference between those ? Well, here is how those various piece
  # of code look like :
  #
  #   "exit"          => [:vcall, :exit]
  #   "Kernel.exit"   => [:call, [:const, :Kernel], :exit]
  #   "Kernel::exit"  => [:call, [:const, :Kernel], :exit]
  #   "k.exit"        => [:call, [:vcall, :k], :exit]
  #   "exit -1"       => [:fcall, :exit, [:array, [:lit, -1]]]
  #
  # Obviously :fcall could be labelled as "function call", :call is a call
  # on to some instance, while vcall might either be a variable dereference
  # or a function call with no arguments.
  #
  # === low-level rules
  #
  # - exclude_symbol : bans the usage of a given symbol (very low-level,
  #                    mostly used by other rules
  # - exclude_head
  # - exclude_fcall
  # - exclude_vcall
  # - exclude_fvcall
  # - exclude_fvccall
  # - exclude_call_on
  # - exclude_call_to
  # - exclude_rebinding
  # - exclude_def
  # - exclude_class_tinkering
  # - exclude_module_tinkering
  #
  # - at_root
  #
  # === higher level rules
  #
  # Those rules take no arguments
  #
  # - exclude_access_to : prevents calling or rebinding a list of classes
  # - exclude_eval : bans eval, module_eval and instance_eval
  # - exclude_global_vars : bans calling or modifying global vars
  # - exclude_alias : bans calls to alias and alias_method
  # - exclude_vm_exiting : bans exit, abort, ...
  # - exclude_raise : bans calls to raise or throw
  #
  #
  # == a bit further
  #
  # It's possible to clone a TreeChecker and to add some more rules to it :
  #
  #   tc0 = Rufus::TreeChecker.new do
  #     #
  #     # calls to eval, module_eval and instance_eval are not allowed
  #     #
  #     exclude_eval
  #   end
  #
  #   tc1 = tc0.clone
  #   tc1.add_rules do
  #     #
  #     # calls to any method on File and FileUtils classes are not allowed
  #     #
  #     exclude_call_on File, FileUtils
  #   end
  #
  class TreeChecker

    VERSION = '1.0.8'

    # pretty-prints the sexp tree of the given rubycode
    #
    def ptree(rubycode)

      puts stree(rubycode)
    end

    # returns the pretty-printed string of the given rubycode
    # (thanks ruby_parser).
    #
    def stree(rubycode)

      "#{rubycode.inspect}\n =>\n#{parse(rubycode).inspect}"
    end

    # initializes the TreeChecker, expects a block
    #
    def initialize(&block)

      @root_set = RuleSet.new
      @set = RuleSet.new
      @current_set = @set

      add_rules(&block)
    end

    def to_s

      s = "#{self.class} (#{self.object_id})\n"
      s << "root_set :\n"
      s << @root_set.to_s
      s << "set :\n"
      s << @set.to_s
    end

    # Performs the check on the given String of ruby code. Will raise a
    # Rufus::SecurityError if there is something excluded by the rules
    # specified at the initialization of the TreeChecker instance.
    #
    def check(rubycode)

      sexp = parse(rubycode)

      #@root_checks.each do |meth, *args|
      #  send meth, sexp, args
      #end
      @root_set.check(sexp)

      do_check(sexp)
    end

    # Return a copy of this TreeChecker instance
    #
    def clone

      Marshal.load(Marshal.dump(self))
    end

    # Adds a set of checks (rules) to this treechecker. Returns self.
    #
    def add_rules(&block)

      instance_eval(&block) if block

      self
    end

    # Freezes the treechecker instance "in depth"
    #
    def freeze

      super
      @root_set.freeze
      @set.freeze
    end

    protected

    class RuleSet

      # Mostly for easier specs
      #
      attr_accessor :excluded_symbols, :accepted_patterns, :excluded_patterns

      def initialize

        @excluded_symbols = {} # symbol => exclusion_message
        @accepted_patterns = {} # 1st elt of pattern => pattern
        @excluded_patterns = {} # 1st elt of pattern => pattern, excl_message
      end

      def exclude_symbol(s, message)

        @excluded_symbols[s] = (message || ":#{s} is excluded")
      end

      def accept_pattern(pat)

        (@accepted_patterns[pat.first] ||= []) << pat
      end

      def exclude_pattern(pat, message)

        (@excluded_patterns[pat.first] ||= []) << [
          pat, message || "#{pat.inspect} is excluded" ]
      end

      def check(sexp)

        if sexp.is_a?(Symbol) and m = @excluded_symbols[sexp]

          raise SecurityError.new(m)

        elsif sexp.is_a?(Array)

          # accepted patterns are evaluated before excluded patterns
          # if one is found the excluded patterns are skipped

          pats = @accepted_patterns[sexp.first] || []
          return false if pats.find { |pat| check_pattern(sexp, pat) }

          pats = @excluded_patterns[sexp.first] || []

          pats.each do |pat, msg|
            raise SecurityError.new(msg) if check_pattern(sexp, pat)
          end
        end

        true
      end

      def freeze

        super

        @excluded_symbols.freeze
        @excluded_symbols.each { |k, v| k.freeze; v.freeze }
        @accepted_patterns.freeze
        @accepted_patterns.each { |k, v| k.freeze; v.freeze }
        @excluded_patterns.freeze
        @excluded_patterns.each { |k, v| k.freeze; v.freeze }
      end

      def to_s

        s = "#{self.class} (#{self.object_id})\n"
        s << "  excluded symbols :\n"
        @excluded_symbols.each do |k, v|
          s << "    - #{k.inspect}, #{v}\n"
        end
        s << "  accepted patterns :\n"
        @accepted_patterns.each do |k, v|
          v.each do |p|
            s << "    - #{k.inspect}, #{p.inspect}\n"
          end
        end
        s << "  excluded patterns :\n"
        @excluded_patterns.each do |k, v|
          v.each do |p|
            s << "    - #{k.inspect}, #{p.inspect}\n"
          end
        end
        s
      end

      # Mostly a spec method
      #
      def ==(oth)

        @excluded_symbols == oth.instance_variable_get(:@excluded_symbols) &&
        @accepted_patterns == oth.instance_variable_get(:@accepted_patterns) &&
        @excluded_patterns == oth.instance_variable_get(:@excluded_patterns)
      end

      protected

      def check_pattern(sexp, pat)

        return false if sexp.length < pat.length

        (1..pat.length - 1).each do |i|
          #puts '.'
          #p (pat[i], sexp[i])
          #p (pat[i] != :any and pat[i] != sexp[i])
          return false if (pat[i] != :any and pat[i] != sexp[i])
        end

        true # we have a match
      end
    end

    #--
    # the methods used to define the checks
    #++

    # Within the 'at_root' block, rules are added to the @root_checks, ie
    # they are evaluated only for the toplevel (root) sexp.
    #
    def at_root(&block)

      @current_set = @root_set
      add_rules(&block)
      @current_set = @set
    end

    def extract_message(args)

      message = nil
      args = args.dup
      message = args.pop if args.last.is_a?(String)
      [ args, message ]
    end

    def expand_class(arg)

      if arg.is_a?(Class) or arg.is_a?(Module)
        [ parse(arg.to_s), parse("::#{arg.to_s}") ]
      else
        [ arg ]
      end
    end

    # Adds a rule that will forbid sexps that begin with the given head
    #
    #     tc = TreeChecker.new do
    #       exclude_head [ :block ]
    #     end
    #
    #     tc.check('a = 2')         # ok
    #     tc.check('a = 2; b = 5')  # will raise an error as it's a block
    #
    def exclude_head(head, message=nil)

      @current_set.exclude_pattern(head, message)
    end

    def exclude_symbol(*args)

      args, message = extract_message(args)
      args.each { |a| @current_set.exclude_symbol(a, message) }
    end

    def exclude_fcall(*args)

      do_exclude_pair(:fcall, args)
    end

    def exclude_vcall(*args)

      do_exclude_pair(:vcall, args)
    end

    def exclude_fvcall(*args)

      do_exclude_pair(:fcall, args)
      do_exclude_pair(:vcall, args)
    end

    def exclude_call_on(*args)

      do_exclude_pair(:call, args)
    end

    def exclude_call_to(*args)

      args, message = extract_message(args)
      args.each { |a| @current_set.exclude_pattern([ :call, :any, a], message) }
    end

    def exclude_fvccall(*args)

      exclude_fvcall(*args)
      exclude_call_to(*args)
    end

    # This rule :
    #
    #     exclude_rebinding Kernel
    #
    # will raise a security error for those pieces of code :
    #
    #     k = Kernel
    #     k = ::Kernel
    #
    def exclude_rebinding(*args)

      args, message = extract_message(args)

      args.each do |a|
        expand_class(a).each do |c|
          @current_set.exclude_pattern([ :lasgn, :any, c], message)
        end
      end
    end

    #
    # prevents access (calling methods and rebinding) to a class (or a list
    # of classes
    #
    def exclude_access_to(*args)

      exclude_call_on *args
      exclude_rebinding *args
    end

    # Bans method definitions
    #
    def exclude_def

      @current_set.exclude_symbol(:defn, 'method definitions are forbidden')
    end

    # Bans the definition and the [re]opening of classes
    #
    # a list of exceptions (classes) can be passed. Subclassing those
    # exceptions is permitted.
    #
    #     exclude_class_tinkering :except => [ String, Array ]
    #
    def exclude_class_tinkering (*args)

      @current_set.exclude_pattern(
        [ :sclass ], 'opening the metaclass of an instance is forbidden')

      Array(args.last[:except]).each { |e|
        expand_class(e).each do |c|
          @current_set.accept_pattern([ :class, :any, c ])
        end
      } if args.last.is_a?(Hash)

      @current_set.exclude_pattern(
        [ :class ], 'defining a class is forbidden')
    end

    # Bans the definition or the opening of modules
    #
    def exclude_module_tinkering

      @current_set.exclude_symbol(
        :module, 'defining or opening a module is forbidden')
    end

    # Bans referencing or setting the value of global variables
    #
    def exclude_global_vars

      @current_set.accept_pattern([ :gvar, :$! ])
        # "rescue => e" is accepted

      @current_set.exclude_symbol(:gvar, 'global vars are forbidden')
      @current_set.exclude_symbol(:gasgn, 'global vars are forbidden')
    end

    # Bans the usage of 'alias'
    #
    def exclude_alias

      @current_set.exclude_symbol(:alias, "'alias' is forbidden")
      @current_set.exclude_symbol(:alias_method, "'alias_method' is forbidden")
    end

    # Bans the use of 'eval', 'module_eval' and 'instance_eval'
    #
    def exclude_eval

      exclude_call_to(:eval, 'eval() is forbidden')
      exclude_call_to(:module_eval, 'module_eval() is forbidden')
      exclude_call_to(:instance_eval, 'instance_eval() is forbidden')
    end

    # Bans the use of backquotes
    #
    def exclude_backquotes

      @current_set.exclude_symbol(:xstr, 'backquotes are forbidden')
      @current_set.exclude_symbol(:dxstr, 'backquotes are forbidden')
    end

    # Bans raise and throw
    #
    def exclude_raise

      exclude_fvccall(:raise, 'raise is forbidden')
      exclude_fvccall(:throw, 'throw is forbidden')
    end

    def do_exclude_pair (first, args)

      args, message = extract_message(args)
      args.each do |a|
        expand_class(a).each do |c|
          @current_set.exclude_pattern([ first, c ], message)
        end
      end
    end

    # The actual check method, check() is rather a bootstrap one...
    #
    def do_check(sexp)

      continue = @set.check(sexp)

      return unless continue
        # found an accepted pattern, no need to dive into it

      return unless sexp.is_a?(Array)
        # check over, seems fine...

      #
      # check children

      sexp.each { |c| do_check(c) }
    end

    # A simple parse (relies on ruby_parser currently)
    #
    def parse(rubycode)

      self.class.parse(rubycode)
    end

    # A simple parse (relies on ruby_parser currently)
    #
    def self.parse(rubycode)

      RubyParser.new.parse(rubycode).to_a
    end
  end
end

