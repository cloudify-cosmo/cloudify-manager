require 'test_helper'
require 'tins/xt'

module Tins
  class RoundTest < Test::Unit::TestCase

    def test_standard
      assert_equal(1, 1.round)
      assert_equal(-1, -1.round)
      assert_equal(2, 1.5.round)
      assert_kind_of Integer, 1.5.round
      assert_equal(-1, -1.4.round)
      assert_equal(-2, -1.5.round)
    end

    def test_inclusion
      assert_equal(10, 12.round(-1))
      assert_kind_of Integer, 12.round(-1)
      assert_equal(-10, -12.round(-1))
      assert_raises(ArgumentError) { 12.round(-2) }
      assert_raises(ArgumentError) { -12.round(-2) }
      assert_in_delta(1.6, 1.55.round(1), 1E-1)
      assert_kind_of Float, 1.55.round(1)
      assert_equal(2, 1.55.round(0))
      assert_in_delta(-1.5, -1.45.round(1), 1E-1)
      assert_equal(-1, -1.45.round(0))
      assert_in_delta(-1.6, -1.55.round(1), 1E-1)
      assert_equal(-2, -1.55.round(0))
      assert_in_delta(-1.55, -1.55.round(999), 1E-2)
    end
  end
end
