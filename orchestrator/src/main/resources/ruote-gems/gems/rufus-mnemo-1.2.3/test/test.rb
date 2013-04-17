
#
# Testing rufus-mnemo
#
# Sun Mar 18 13:29:37 JST 2007
#

$:.unshift(File.expand_path('../../lib', __FILE__))

require 'test/unit'
require 'rufus/mnemo'

#
# testing misc things
#
class MnemoTest < Test::Unit::TestCase

  def test_from_integer

    t = Time.now
    #puts t.to_f

    st = t.to_f * 1000 * 10

    #puts st

    st = Integer(st) % (10 * 1000 * 60 * 60)
    #st = 28340469

    s = Rufus::Mnemo::from_integer(st)

    st2 = Rufus::Mnemo::to_integer(s)
    s2 = Rufus::Mnemo::from_integer(st2)

    assert_equal s, s2
    assert_equal st, st2
  end

  def test_is_mnemo_word

    assert Rufus::Mnemo::is_mnemo_word('takeshi')

    assert Rufus::Mnemo::is_mnemo_word('tsunasima')
    assert Rufus::Mnemo::is_mnemo_word('tunashima')

    assert (not Rufus::Mnemo::is_mnemo_word('dsfadf'))
    assert (not Rufus::Mnemo::is_mnemo_word('takeshin'))
  end

  def test_split

    assert_equal %w[ ko chi pi ga ], Rufus::Mnemo.split('kochipiga')
    assert_equal %w[ ko na de tzu ], Rufus::Mnemo.split('konadetzu')
  end

  def test_zero

    assert_equal '', Rufus::Mnemo::from_integer(0)
    assert_equal 0, Rufus::Mnemo::to_integer('')
  end

  def test_negatives

    assert_equal -35, Rufus::Mnemo::to_integer('wina')
    assert_equal 'wina', Rufus::Mnemo::from_integer(-35)

    assert_equal -1, Rufus::Mnemo::to_integer('wibe')
    assert_equal 'wibe', Rufus::Mnemo::from_integer(-1)
  end

  def test_wi_bad_position

    %w(wi wiwi bewi nawi nabewi nawibe nawiwi).each do |bad_mnemo|

      error = assert_raise RuntimeError do
        Rufus::Mnemo::to_integer(bad_mnemo)
      end
      assert_equal "did not find syllable 'wi'", error.to_s
    end
  end

  def test_collision_with_mathn

    assert_equal 'dobejotehozi',  Rufus::Mnemo._from_integer(13477774722)

    require 'mathn'

    assert_equal 'dobejotehozi',  Rufus::Mnemo._from_integer(13477774722)
  end

  def test_aliases_i_to_s

    assert_equal 'wina', Rufus::Mnemo.from_integer(-35)
    assert_equal 'wina', Rufus::Mnemo.from_i(-35)
    assert_equal 'wina', Rufus::Mnemo.to_string(-35)
    assert_equal 'wina', Rufus::Mnemo.to_s(-35)

    assert_equal 'dobejotehotzu',  Rufus::Mnemo.from_integer(13477774722)
    assert_equal 'dobejotehotzu',  Rufus::Mnemo.from_i(13477774722)
    assert_equal 'dobejotehotzu',  Rufus::Mnemo.to_string(13477774722)
    assert_equal 'dobejotehotzu',  Rufus::Mnemo.to_s(13477774722)
  end

  def test_aliases_s_to_i

    assert_equal -35, Rufus::Mnemo.from_string('wina')
    assert_equal -35, Rufus::Mnemo.from_s('wina')
    assert_equal -35, Rufus::Mnemo.to_integer('wina')
    assert_equal -35, Rufus::Mnemo.to_i('wina')

    assert_equal 13477774722, Rufus::Mnemo.from_string('dobejotehotzu')
    assert_equal 13477774722, Rufus::Mnemo.from_s('dobejotehotzu')
    assert_equal 13477774722, Rufus::Mnemo.to_integer('dobejotehotzu')
    assert_equal 13477774722, Rufus::Mnemo.to_i('dobejotehotzu')
  end
end

