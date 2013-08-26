
# rufus-mnemo #

This gem provides methods for turning integer into easier to remember 'words' and vice-versa.

The module Rufus::Mnemo has all the explanation.


## getting it ##

    gem install rufus-mnemo


## usage ##

    require 'rubygems'
    require 'rufus/mnemo'

    p Rufus::Mnemo.from_integer(125704)
    p Rufus::Mnemo.from_i(125704)
    p Rufus::Mnemo.to_s(125704)
      # => 'karasu'

    p Rufus::Mnemo.to_integer('karasu')
    p Rufus::Mnemo.to_i('karasu')
    p Rufus::Mnemo.from_s('karasu')
      # => 125704


## about negative integers ##

They are prefixed with the "wi" syllable (Thanks Stephan Wehner).

    p Rufus::Mnemo.from_integer(-173866)
    p Rufus::Mnemo.to_s(-173866)
      # => 'winamote'


## ports in other languages ##

* PHP: https://github.com/aleksblendwerk/mnemo by Alexander Seltenreich


## dependencies ##

None.


## mailing list ##

On the rufus-ruby list:

http://groups.google.com/group/rufus-ruby


## IRC ##

On freenode.net, the #ruote channel


## issue tracker ##

https://github.com/jmettraux/rufus-mnemo/issues


## source ##

http://github.com/jmettraux/rufus-mnemo


## author ##

John Mettraux, jmettraux@gmail.com, http://lambda.io/jmettraux


## the rest of Rufus ##

http://rufus.rubyforge.org


## license ##

MIT

