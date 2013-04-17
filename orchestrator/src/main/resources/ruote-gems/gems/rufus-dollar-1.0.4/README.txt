
= rufus-dollar

A one-method library for substituting ${stuff} in text strings.


== getting it

  gem install rufus-dollar

or at

http://rubyforge.org/frs/?group_id=4812


== usage

  require 'rubygems'
  require 'rufus/dollar'
  
  h = {
    'name' => 'Fred Brooks',
    'title' => 'Silver Bullet',
    'left' => 'na',
    'right' => 'me',
  }
  
  puts Rufus::dsub "${name} wrote '${title}'", h
    # => "Fred Brooks wrote 'Silver Bullet'"
  
  # dollar notations are nestable
  
  puts Rufus::dsub "${${left}${right}}", h
    # => "${name}" => "Fred Brooks"

  # prefixing the key with a ' or a " makes it quotable

  puts Rufus::dsub "${name} wrote ${'title}", h
    # => 'Fred Brooks wrote "Silver Bullet"'


== dependencies

None.


== mailing list

On the rufus-ruby list[http://groups.google.com/group/rufus-ruby] :

  http://groups.google.com/group/rufus-ruby


== issue tracker

http://rubyforge.org/tracker/?atid=18584&group_id=4812&func=browse


== source

http://github.com/jmettraux/rufus-dollar

  git clone git://github.com/jmettraux/rufus-dollar.git


== author

John Mettraux, jmettraux@gmail.com 
http://jmettraux.wordpress.com


== the rest of Rufus

http://rufus.rubyforge.org


== license

MIT

