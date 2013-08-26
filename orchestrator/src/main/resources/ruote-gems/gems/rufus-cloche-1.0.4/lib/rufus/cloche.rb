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

require 'thread'
require 'fileutils'

#require 'rufus-json/automatic'
  # best left to the code using rufus-cloche, not to rufus-cloche itself

require 'rufus/cloche/version'


module Rufus

  #
  # A cloche is a local JSON hashes store.
  #
  # Warning : cloches are process-safe but not thread-safe.
  #
  class Cloche

    WIN = (RUBY_PLATFORM.match(/mswin|mingw/) != nil)

    attr_reader :dir

    # Creates a new 'cloche'.
    #
    # There are 2 options :
    #
    # * :dir : to specify the directory into which the cloche data is store
    # * :nolock : when set to true, no flock is used
    #
    # On the Windows platform, :nolock is set to true automatically.
    #
    def initialize(opts={})

      @dir = File.expand_path(opts[:dir] || 'cloche')
      @mutex = Mutex.new

      @nolock = WIN || opts[:nolock]
    end

    # Puts a document (Hash) under the cloche.
    #
    # If the document is brand new, it will be given a revision number '_rev'
    # of 0.
    #
    # If the document already exists in the cloche and the version to put
    # has an older (different) revision number than the one currently stored,
    # put will fail and return the current version of the doc.
    #
    # If the put is successful, nil is returned.
    #
    def put(doc, opts={})

      opts = opts.inject({}) { |h, (k, v)| h[k.to_s] = v; h }

      doc = Rufus::Json.dup(doc) unless opts['update_rev']
        # work with a copy, don't touch original

      type, key = doc['type'], doc['_id']

      raise(
        ArgumentError.new("missing values for keys 'type' and/or '_id'")
      ) if type.nil? || key.nil?

      rev = (doc['_rev'] ||= -1)

      raise(
        ArgumentError.new("values for '_rev' must be positive integers")
      ) if rev.class != Fixnum && rev.class != Bignum

      r =
        lock(rev == -1 ? :create : :write, type, key) do |file|

          cur = do_get(file)

          return cur if cur && cur['_rev'] != doc['_rev']
          return true if cur.nil? && doc['_rev'] != -1

          doc['_rev'] += 1

          File.open(file.path, 'wb') { |io| io.write(Rufus::Json.encode(doc)) }
        end

      r == false ? true : nil
    end

    # Gets a document (or nil if not found (or corrupted)).
    #
    def get(type, key)

      r = lock(:read, type, key) { |f| do_get(f) }

      r == false ? nil : r
    end

    # Attempts at deleting a document. You have to pass the current version
    # or at least the { '_id' => i, 'type' => t, '_rev' => r }.
    #
    # Will return nil if the deletion is successful.
    #
    # If the deletion failed because the given doc has an older revision number
    # that the one currently stored, the doc in its freshest version will be
    # returned.
    #
    # Returns true if the deletion failed.
    #
    def delete(doc)

      drev = doc['_rev']

      raise ArgumentError.new('cannot delete doc without _rev') unless drev

      type, key = doc['type'], doc['_id']

      r =
        lock(:delete, type, key) do |f|

          cur = do_get(f)

          return nil unless cur
          return cur if cur['_rev'] != drev

          begin
            f.close
            File.delete(f.path)
            nil
          rescue Exception => e
            #p e
            false
          end
        end

      r == false ? true : nil
    end

    # Given a type, this method will return an array of all the documents for
    # that type.
    #
    # A optional second parameter may be used to select, based on a regular
    # expression, which documents to include (match on the key '_id').
    #
    # Will return an empty Hash if there is no documents for a given type.
    #
    # == opts
    #
    # :skip and :limit are understood (pagination).
    #
    # If :count => true, the query will simply return the number of documents
    # that matched.
    #
    def get_many(type, regex=nil, opts={})

      opts = opts.inject({}) { |h, (k, v)| h[k.to_s] = v; h }

      d = dir_for(type)

      return (opts['count'] ? 0 : []) unless File.exist?(d)

      regexes = regex ? Array(regex) : nil

      docs = []
      skipped = 0

      limit = opts['limit']
      skip = opts['skip']
      count = opts['count'] ? 0 : nil

      files = Dir[File.join(d, '**', '*.json')].sort_by { |f| File.basename(f) }
      files = files.reverse if opts['descending']

      files.each do |fn|

        key = File.basename(fn, '.json')

        if regexes.nil? or match?(key, regexes)

          skipped = skipped + 1
          next if skip and skipped <= skip

          doc = get(type, key)
          next unless doc

          if count
            count = count + 1
          else
            docs << doc
          end

          break if limit and docs.size >= limit
        end
      end

      # WARNING : there is a twist here, the filenames may have a different
      #           sort order from actual _ids...

      #docs.sort { |doc0, doc1| doc0['_id'] <=> doc1['_id'] }
        # let's trust filename order

      count ? count : docs
    end

    # Removes entirely documents of a given type.
    #
    def purge_type!(type)

      FileUtils.rm_rf(dir_for(type))
    end

    # Returns a sorted list of all the ids for a given type of documents.
    #
    # Warning : trusts the ids to be identical to the filenames
    #
    def ids(type)

      Dir[File.join(dir_for(type), '**', '*.json')].collect { |path|
        File.basename(path, '.json')
      }.sort
    end

    # Returns a sorted list of all the ids for a given type of documents.
    #
    # Actually reads each file and returns the real _id list
    #
    def real_ids(type)

      Dir[File.join(dir_for(type), '**', '*.json')].inject([]) { |a, p|
        doc = do_get(p)
        a << doc['_id'] if doc
        a
      }.sort
    end

    protected

    def match?(key, regexes)

      regexes.first.is_a?(Regexp) ?
        regexes.find { |regex| regex.match(key) } :
        regexes.find { |s| key[-s.length..-1] == s }
    end

    def self.neutralize(s)

      s.to_s.strip.gsub(/[ \/:;\*\\\+\?]/, '_')
    end

    def do_get(file)

      s = file.is_a?(File) ? file.read : File.read(file)
      Rufus::Json.decode(s) rescue nil
    end

    def dir_for(type)

      File.join(@dir, Cloche.neutralize(type || 'no_type'))
    end

    def path_for(type, key)

      nkey = Cloche.neutralize(key)

      subdir = (nkey[-2, 2] || nkey).gsub(/\./, 'Z')

      [ File.join(dir_for(type), subdir), "#{nkey}.json" ]
    end

    def lock(ltype, type, key, &block)

      @mutex.synchronize do
        begin

          d, f = path_for(type, key)
          fn = File.join(d, f)

          FileUtils.mkdir_p(d) if ltype == :create && ( ! File.exist?(d))
          FileUtils.touch(fn) if ltype == :create && ( ! File.exist?(fn))

          file = File.new(fn, 'r+') rescue nil

          return false if file.nil?

          file.flock(File::LOCK_EX) unless @nolock

          if ltype == :write
            Thread.pass
            21.times { return false unless File.exist?(fn) }
          end
            #
            # We got the lock, but is the file still here?
            #
            # Asking more than one time, since, at least on OSX snoleo,
            # File.exist? might say yes for a file just deleted
            # (by another process)

          block.call(file)

        ensure
          begin
            file.flock(File::LOCK_UN) unless @nolock
          rescue Exception => e
            #p [ :lock, @fpath, e ]
            #e.backtrace.each { |l| puts l }
          end
          begin
            file.close if file
          rescue Exception => e
            #p [ :close_fail, e ]
          end
        end
      end
    end
  end
end

