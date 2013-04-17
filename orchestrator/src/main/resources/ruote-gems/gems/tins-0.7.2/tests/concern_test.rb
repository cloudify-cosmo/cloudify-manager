require 'test_helper'
require 'tins/concern'

module Tins
  class ConcernTest < Test::Unit::TestCase
    module ConcernTroll
      extend ::Tins::Concern

      included do
        @included = :included
      end

      module ClassMethods
        def class_foo
          :class_foo
        end
      end

      def foo
        :foo
      end
    end

    class Troll
      include ConcernTroll
    end

    def test_concern
      assert_equal :class_foo, Troll.class_foo
      assert_equal :foo, Troll.new.foo
      assert_equal :included, Troll.instance_variable_get(:@included)
    end
  end
end
