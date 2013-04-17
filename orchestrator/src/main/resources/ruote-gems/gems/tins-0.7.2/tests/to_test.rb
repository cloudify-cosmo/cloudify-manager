require 'test_helper'
require 'tins/xt/to'

module Tins
  class ToTest < Test::Unit::TestCase
    def test_to_removing_leading_spaces
      doc = to(<<-end)
        hello, world
      end
      assert_equal "hello, world\n", doc
    end

    def test_to_not_removing_empty_lines
      doc = to(<<-end)
        hello, world

        another line
      end
      assert_equal "hello, world\n\nanother line\n", doc
    end
  end
end
