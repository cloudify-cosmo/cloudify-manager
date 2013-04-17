module Tins
  module To
    def to(string)
      string.gsub(/^[^\S\n]*/, '')
    end
  end
end
