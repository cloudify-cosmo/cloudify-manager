require 'date'

module Tins
  module DateDummy
    def self.included(modul)
      class << modul
        alias really_today today

        remove_method :today rescue nil

        attr_writer :dummy

        def dummy(value = nil)
          if value.nil?
            @dummy
          else
            begin
              old_dummy = @dummy
              @dummy = value
              yield
            ensure
              @dummy = old_dummy
            end
          end
        end

        def today
          if dummy
            dummy.dup
          else
            really_today
          end
        end

        end
      super
    end
  end
end

require 'tins/alias'

