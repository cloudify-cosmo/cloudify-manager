
#
# Specifying rufus-treechecker
#
# Wed Dec 22 15:49:08 JST 2010
#

require File.join(File.dirname(__FILE__), 'spec_base')


describe Rufus::TreeChecker do

  describe 'exclude_global_vars' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_global_vars
      end
    end

    it 'does not block "1 + 1"' do

      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    it 'does not block begin/rescue/end' do

      tc.check(%{
        begin
        rescue => e
        end
      })
    end

    [

      "$ENV",
      "$ENV = {}",
      "$ENV['HOME'] = 'away'"

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_alias' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_alias
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'alias a b',
      'alias :a :b',
      'alias_method :a, :b',
      'alias_method "a", "b"'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_class_tinkering' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_class_tinkering
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'class << instance; def length; 3; end; end',
      'class Toto; end',
      'class Alpha::Toto; end'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_class_tinkering :except => [ String ]' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_class_tinkering :except => [ String, Rufus::TreeChecker ]
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'class S2 < String; def length; 3; end; end',
      'class Toto < Rufus::TreeChecker; def length; 3; end; end',

    ].each do |code|

      it "doesn't block '#{code}'" do
        lambda { tc.check(code) }.should_not raise_error
      end
    end

    [

      'class String; def length; 3; end; end',

      'class Toto; end',
      'class Alpha::Toto; end'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_module_tinkering' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_module_tinkering
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'module Alpha; end',
      'module Momo::Alpha; end'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_eval' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_eval
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'eval("code")',
      'Kernel.eval("code")',
      'toto.instance_eval("code")',
      'Toto.module_eval("code")'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_backquotes' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_backquotes
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      '`kill -9 whatever`',
      '[ 1, 2, 3 ].each { |i| `echo #{i}.txt` }'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_raise' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_raise
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'Kernel.puts "error"'

    ].each do |code|

      it "doesn't block '#{code}'" do
        lambda { tc.check(code) }.should_not raise_error
      end
    end

    [

      'raise',
      'raise "error"',
      'Kernel.raise',
      'Kernel.raise "error"',
      'throw',
      'throw :halt'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_rebinding' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_call_to :class
        exclude_rebinding Kernel, Rufus::TreeChecker
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'k = Kernel',
      'k = ::Kernel',
      'c = Rufus::TreeChecker',
      'c = ::Rufus::TreeChecker',
      's = "".class'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_access_to(File)' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_access_to File
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'f = File',
      'f = ::File',
      'File.read "hello.txt"',
      '::File.read "hello.txt"'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end
end

