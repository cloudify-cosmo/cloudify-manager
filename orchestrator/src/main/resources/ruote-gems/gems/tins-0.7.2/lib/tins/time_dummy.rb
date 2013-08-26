require 'time'

module Tins
  module TimeDummy
    def self.included(modul)
      class << modul
        alias really_new new
        alias really_now now

        remove_method :now rescue nil
        remove_method :new rescue nil

        attr_writer :dummy

        def dummy=(value)
          if value.respond_to?(:to_str)
            value = Time.parse(value.to_str)
          end
          @dummy = value
        end

        def dummy(value = nil)
          if value.nil?
            @dummy
          else
            begin
              old_dummy = @dummy
              self.dummy = value
              yield
            ensure
              self.dummy = old_dummy
            end
          end
        end

        def new(*a)
          if dummy
            dummy.dup
          elsif caller.first =~ /now/
            really_now
          else
            really_new(*a)
          end
        end

        def now
          new
        end
      end
      super
    end
  end
end

require 'tins/alias'
