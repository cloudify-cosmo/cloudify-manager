#--
# Copyright (c) 2009-2013, John Mettraux, jmettraux@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Made in Japan.
#++

require 'ostruct'


module Rufus
module Json

  VERSION = '1.0.4'

  # The JSON / JSON pure decoder
  #
  JSON = OpenStruct.new(
    :encode => lambda { |o, opts|
      opts[:max_nesting] = false unless opts.has_key?(:max_nesting)
      if o.is_a?(Hash) or o.is_a?(Array)
        ::JSON.generate(o, opts)
      else
        ::JSON.generate([ o ], opts).strip[1..-2]
      end
    },
    :pretty_encode => lambda { |o|
      encode(
        o,
        :indent => '  ', :object_nl => "\n", :array_nl => "\n", :space => ' ')
    },
    :decode => lambda { |s|
      ::JSON.parse(
        "[#{s}]",
        :max_nesting => nil,
        :create_additions => false
      ).first },
    :error => lambda {
      ::JSON::ParserError }
  )

  # The Rails ActiveSupport::JSON decoder
  #
  ACTIVE_SUPPORT = OpenStruct.new(
    :encode => lambda { |o, opts|
      ActiveSupport::JSON.encode(o, opts) },
    :pretty_encode => lambda { |o|
      ActiveSupport::JSON.encode(o) },
    :decode => lambda { |s|
      decode_e(s) || ActiveSupport::JSON.decode(s) },
    :error => lambda {
      RuntimeError }
  )
  ACTIVE = ACTIVE_SUPPORT

  # https://github.com/brianmario/yajl-ruby/
  #
  YAJL = OpenStruct.new(
    :encode => lambda { |o, opts|
      Yajl::Encoder.encode(o, opts) },
    :pretty_encode => lambda { |o|
      Yajl::Encoder.encode(o, :pretty => true, :indent => '  ') },
    :decode => lambda { |s|
      Yajl::Parser.parse(s) },
    :error => lambda {
      ::Yajl::ParseError }
  )

  # https://github.com/ohler55/oj
  #
  OJ = OpenStruct.new(
    :encode => lambda { |o, opts|
      Oj.dump(syms_to_s(o), opts.merge(:symbol_keys => false)) },
    :pretty_encode => lambda { |o|
      Oj.dump(syms_to_s(o), :indent => 2) },
    :decode => lambda { |s|
      Oj.load(s, :strict => true) },
    :error => lambda {
      ::Oj::ParseError }
  )

  # The "raise an exception because there's no backend" backend
  #
  NONE = OpenStruct.new(
    :encode => lambda { |o, opts| raise 'no JSON backend found' },
    :pretty_encode => lambda { |o| raise 'no JSON backend found' },
    :decode => lambda { |s| raise 'no JSON backend found' },
    :error => lambda { raise 'no JSON backend found' }
  )

  # In the given order, attempts to load a json lib and sets it as the
  # backend of rufus-json.
  #
  # Returns the name of lib found if sucessful.
  #
  # Returns nil if no lib could be set.
  #
  # The default order / list of backends is yajl, active_support, json,
  # json/pure. When specifying a custom order/list, unspecified backends
  # won't be tried for.
  #
  def self.load_backend(*order)

    order = %w[ yajl active_support json json/pure ] if order.empty?

    order.each do |lib|
      begin
        require(lib)
        Rufus::Json.backend = lib
        return lib
      rescue LoadError => le
      end
    end

    nil
  end

  # [Re-]Attempts to detect a JSON backend
  #
  def self.detect_backend

    @backend = if defined?(::Oj)
      OJ
    elsif defined?(::Yajl)
      YAJL
    elsif defined?(::JSON)
      JSON
    elsif defined?(ActiveSupport::JSON)
      ACTIVE_SUPPORT
    else
      NONE
    end
  end

  detect_backend
    # run it right now

  # Returns true if there is a backend set for parsing/encoding JSON
  #
  def self.has_backend?

    (@backend != NONE)
  end

  # Returns :yajl|:json|:active|:none (an identifier for the current backend)
  #
  def self.backend

    %w[ yajl json active oj none ].find { |b|
      Rufus::Json.const_get(b.upcase) == @backend
    }.to_sym
  end

  # Forces a decoder JSON/ACTIVE_SUPPORT or any lambda pair that knows
  # how to deal with JSON.
  #
  # It's OK to pass a symbol as well, :yajl, :json, :active (or :none).
  #
  def self.backend=(b)

    b = {
      'yajl' => YAJL, 'yajl-ruby' => YAJL,
      'json' => JSON, 'json-pure' => JSON,
      'active' => ACTIVE, 'active-support' => ACTIVE,
      'oj' => OJ, 'none' => NONE
    }[b.to_s.gsub(/[_\/]/, '-')] if b.is_a?(String) or b.is_a?(Symbol)

    @backend = b
  end

  # Encodes the given object to a JSON string.
  #
  def self.encode(o, opts={})

    @backend.encode[o, opts]
  end

  # Pretty encoding
  #
  def self.pretty_encode(o)

    @backend.pretty_encode[o]
  end

  # An alias for .encode
  #
  def self.dump(o, opts={})

    encode(o, opts)
  end

  # Decodes the given JSON string.
  #
  def self.decode(s)

    @backend.decode[s]

  rescue @backend.error[] => e
    raise ParserError.new(e.message)
  end

  # An alias for .decode
  #
  def self.load(s)

    decode(s)
  end

  # Duplicates an object by turning it into JSON and back.
  #
  # Don't laugh, yajl-ruby makes that faster than a Marshal copy.
  #
  def self.dup(o)

    (@backend == NONE) ? Marshal.load(Marshal.dump(o)) : decode(encode(o))
  end

  E_REGEX = /^\d+(\.\d+)?[eE][+-]?\d+$/

  # Let's ActiveSupport do the E number notation.
  #
  def self.decode_e(s)

    s.match(E_REGEX) ? eval(s) : false
  end

  # Used to get a uniform behaviour among encoders.
  #
  def self.syms_to_s(o)

    return o.to_s if o.is_a?(Symbol)
    return o unless o.is_a?(Hash)

    o.inject({}) { |h, (k, v)| h[k.to_s] = syms_to_s(v); h }
  end

  # Wraps parser errors during decode
  #
  class ParserError < StandardError; end
end
end

