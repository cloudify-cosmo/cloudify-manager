
#
# Specifying rufus-treechecker
#
# Wed Dec 22 15:49:08 JST 2010
#

require File.join(File.dirname(__FILE__), 'spec_base')


describe Rufus::TreeChecker do

  describe 'exclude_call_to(:exit)' do

    let :tc do
      Rufus::TreeChecker.new do
        #exclude_vcall :abort
        #exclude_fcall :abort
        exclude_call_to :abort
        #exclude_fvcall :exit, :exit!
        exclude_call_to :exit
        exclude_call_to :exit!
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    %w[

      exit exit() exit(1)
      exit! exit!() exit!(1)
      Kernel.exit Kernel.exit() Kernel.exit(1)
      ::Kernel.exit ::Kernel.exit() ::Kernel.exit(1)

      abort abort() abort("damn!")
      Kernel.abort Kernel.abort() Kernel.abort(1)
      ::Kernel.abort ::Kernel.abort() ::Kernel.abort(1)

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_call_on' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_call_on File, FileUtils
        exclude_call_on IO
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'data = File.read("surf.txt")',
      'f = File.new("surf.txt")',
      'FileUtils.rm_f("bondzoi.txt")',
      'IO.foreach("testfile") {|x| print "GOT ", x }'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_def' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_def
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'def drink; "water"; end',
      'class Toto; def drink; "water"; end; end',
      %{
class Whatever
  def eat
    "food"
  end
end
      }

    ].each do |code|

      it "blocks #{code.inspect}" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_fvccall (public/protected/private)' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_fvccall :public
        exclude_fvccall :protected
        exclude_fvccall :private
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'public',
      'public :surf',
      'class Toto; public :car; end',
      'private',
      'private :surf',
      'class Toto; private :car; end'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'exclude_head' do

    let :tc do
      Rufus::TreeChecker.new do
        exclude_head [ :block ]
        exclude_head [ :lasgn ]
        exclude_head [ :dasgn_curr ]
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [

      'a; b; c',
      'lambda { a; b; c }',

      'a = 2',
      'lambda { a = 2 }'

    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end

  describe 'at_root { }' do

    let :tc do
      Rufus::TreeChecker.new do
        at_root do
          exclude_head [ :block ]
          exclude_head [ :lasgn ]
        end
      end
    end

    it 'does not block "1 + 1"' do
      lambda { tc.check("1 + 1") }.should_not raise_error
    end

    [
      'lambda { a; b; c }',
      'lambda { a = 2 }'
    ].each do |code|

      it "doesn't block '#{code}'" do
        lambda { tc.check(code) }.should_not raise_error
      end
    end

    [
      'a; b; c',
      'a = 2'
    ].each do |code|

      it "blocks '#{code}'" do
        lambda { tc.check(code) }.should raise_error(Rufus::SecurityError)
      end
    end
  end
end

