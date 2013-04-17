require 'test_helper'
require 'tins'

module Tins
  class NullTest < Test::Unit::TestCase
    require 'tins/xt/null'

    def test_null
      assert_equal NULL, NULL.foo
      assert_equal NULL, NULL.foo.bar
      assert_equal 'NULL', NULL.inspect
      assert_equal '', NULL.to_s
      assert_equal 0, NULL.to_i
      assert_equal 0.0, NULL.to_f
      assert_equal [], NULL.to_a
      assert_equal 1, Null(1)
      assert_equal NULL, Null(nil)
      assert_equal NULL, NULL::NULL
      assert NULL.nil?
      assert NULL.blank?
    end
  end
end
