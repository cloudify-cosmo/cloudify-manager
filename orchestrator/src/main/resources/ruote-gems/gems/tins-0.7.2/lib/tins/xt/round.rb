require 'tins/round'

module Tins
  module Round
    class ::Float
      include Round
    end

    class ::Integer
      include Round
    end
  end
end
