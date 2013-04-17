module Tins
  # Implementation of the null object pattern in Ruby.
  module Null
    def method_missing(*)
      self
    end

    def const_missing(*)
      self
    end

    def to_s
      ''
    end

    def to_str
      nil
    end

    def to_f
      0.0
    end

    def to_i
      0
    end

    def to_int
      nil
    end

    def to_a
      []
    end

    def to_ary
      nil
    end

    def inspect
      'NULL'
    end

    def nil?
      true
    end

    def blank?
      true
    end

    module Kernel
      def Null(value = nil)
        value.nil? ? Tins::NULL : value
      end
    end
  end

  class NullClass < Module
    include Tins::Null
  end

  NULL = NullClass.new.freeze
end

require 'tins/alias'
