require 'test_helper'
require 'tins'

module Tins
  class MemoizeTest < Test::Unit::TestCase
    class FooBar
      def foo(*a)
        @@foo ||= 0
        @@foo += 1
      end
      memoize_method :foo

      def bar(*a)
        @@bar ||= 0
        @@bar += 1
      end
      memoize_function :bar
    end

    def test_method_cache
      fb1 = FooBar.new
      fb2 = FooBar.new
      assert_equal true, fb1.__memoize_cache__.empty?
      assert_equal true, fb2.__memoize_cache__.empty?
      assert_equal 1, fb1.foo(1, 2)
      assert_equal 2, fb2.foo(1, 2)
      assert_equal 3, fb1.foo(1, 2, 3)
      assert_equal 4, fb2.foo(1, 2, 3)
      assert_equal 1, fb1.foo(1, 2)
      assert_equal 2, fb2.foo(1, 2)
      fb1.memoize_cache_clear
      fb2.memoize_cache_clear
      assert_equal true, fb1.__memoize_cache__.empty?
      assert_equal true, fb2.__memoize_cache__.empty?
      assert_equal 5, fb1.foo(1, 2)
      assert_equal 6, fb2.foo(1, 2)
      assert_equal 5, fb1.foo(1, 2)
      assert_equal 6, fb2.foo(1, 2)
      assert_equal false, fb1.__memoize_cache__.empty?
      assert_equal false, fb2.__memoize_cache__.empty?
    end

    def test_function_cache
      fb1 = FooBar.new
      fb2 = FooBar.new
      assert_equal 1, fb1.bar(1, 2)
      assert_equal 1, fb2.bar(1, 2)
      assert_equal 2, fb1.bar(1, 2, 3)
      assert_equal 2, fb2.bar(1, 2, 3)
      assert_equal 1, fb1.bar(1, 2)
      assert_equal 1, fb2.bar(1, 2)
      FooBar.memoize_cache_clear
      assert_equal 3, fb1.bar(1, 2)
      assert_equal 3, fb2.bar(1, 2)
      assert_equal false, FooBar.__memoize_cache__.empty?
    end
  end
end
