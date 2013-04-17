module Tins
  # A bit more versatile rounding for Ruby
  module Round
    def self.included(klass)
      if klass.instance_method(:round)
        klass.class_eval do
          begin
            alias_method :__old_round__, :round
            remove_method :round
          rescue NameError
          end
        end
        super
      else
        raise NoMethodError, 'no round method found'
      end
    end

    def round(places = nil)
      if places == nil || places == 0
        return __old_round__
      elsif places.respond_to?(:to_int)
        places = places.to_int
      else
        raise TypeError, "argument places has to be like an Integer"
      end
      if places < 0
        max_places = -Math.log(self.abs + 1) / Math.log(10)
        raise ArgumentError, "places has to be >= #{max_places.ceil}" if max_places > places
      end
      t = self
      f = 10.0 ** places
      t *= f
      if t.infinite?
        result = self
      else
        if t >= 0.0
          t = (t + 0.5).floor
        elsif t < 0.0
          t = (t - 0.5).ceil
        end
        t /= f
        result = t.nan? ? self : t
      end
      max_places and result = result.to_i # if places < 0
      result
    end
  end
end

require 'tins/alias'
