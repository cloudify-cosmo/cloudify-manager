require 'test_helper'
require 'tins/xt'

module Tins
  class AskAndSendTest < Test::Unit::TestCase
    class A
      public

      def foo
        :foo
      end

      private

      def bar
        :bar
      end
    end

    def test_asking_publicly
      assert_equal :foo, A.new.ask_and_send(:foo)
      assert_nil A.new.ask_and_send(:bar)
      assert_nil A.new.ask_and_send(:baz)
    end

    def test_asking_privately
      assert_equal :foo, A.new.ask_and_send!(:foo)
      assert_equal :bar, A.new.ask_and_send!(:bar)
      assert_nil A.new.ask_and_send(:baz)
    end
  end
end
