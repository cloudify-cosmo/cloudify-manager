
= 'rufus-treechecker'

== what is it ?

Initialize a Rufus::TreeChecker and pass some ruby code to make sure it's safe before calling eval().


== getting it

    gem install -y rufus-treechecker

or download[http://rubyforge.org/frs/?group_id=4812] it from RubyForge.


== usage

The treechecker uses ruby_parser (http://rubyforge.org/projects/parsetree)
to turn Ruby code into s-expressions, the treechecker then
checks this sexp tree and raises a Rufus::SecurityError if an excluded pattern
is spotted.

The excluded patterns are defined at the initialization of the TreeChecker
instance by listing rules.

  require 'rubygems'
  require 'rufus-treechecker'

  tc = Rufus::TreeChecker.new do
    exclude_fvcall :abort
    exclude_fvcall :exit, :exit!
  end

  tc.check("1 + 1; abort")               # will raise a SecurityError
  tc.check("puts (1..10).to_a.inspect")  # OK


Nice, but how do I know what to exclude ?

  require 'rubygems'
  require 'rufus-treechecker'

  Rufus::TreeChecker.new.ptree('a = 5 + 6; puts a')

will yield

  "a = 5 + 6; puts a"
   =>
   [:block,
     [:lasgn, :a, [:call, [:lit, 5], :+, [:array, [:lit, 6]]]],
     [:fcall, :puts, [:array, [:lvar, :a]]]
   ]


For more documentation, see http://github.com/jmettraux/rufus-treechecker/tree/master/lib/rufus/treechecker.rb


== dependencies

the 'ruby_parser' gem by Ryan Davis.


== mailing list

On the Rufus-Ruby list[http://groups.google.com/group/rufus-ruby] :

  http://groups.google.com/group/rufus-ruby


== issue tracker

  http://rubyforge.org/tracker/?atid=18584&group_id=4812&func=browse


== source

http://github.com/jmettraux/rufus-treechecker

  git clone git://github.com/jmettraux/rufus-treechecker.git


== author

John Mettraux, jmettraux@gmail.com,
http://jmettraux.wordpress.com


== the rest of Rufus

http://rufus.rubyforge.org


== license

MIT

