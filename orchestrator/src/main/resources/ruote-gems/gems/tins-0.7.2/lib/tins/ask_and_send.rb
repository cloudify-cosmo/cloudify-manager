module Tins
  module AskAndSend
    def ask_and_send(method_name, *args, &block)
      if respond_to?(method_name)
        __send__(method_name, *args, &block)
      end
    end

    def ask_and_send!(method_name, *args, &block)
      if respond_to?(method_name, true)
        __send__(method_name, *args, &block)
      end
    end
  end
end
