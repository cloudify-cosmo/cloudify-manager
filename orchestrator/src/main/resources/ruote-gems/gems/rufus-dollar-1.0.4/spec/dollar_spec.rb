
#
# Specifying rufus-dollar
#
# Tue Dec 21 15:48:43 JST 2010
#

require File.join(File.dirname(__FILE__), 'spec_base')


describe Rufus::Dollar do

  context 'simple usage' do

    let(:dict) do
      {
        'renard' => 'goupil',
        'cane' => 'oie',
        'oie blanche' => 'poule',
        'x' => 'y',
        'customers' => %w[ alice bob ],
        'table' => { 2011 => 2, 2012 => 7 }
      }
    end

    describe '.dsub' do

      it "doesn't substitute if there are no ${}" do

        dsub("le petit renard").should == "le petit renard"
      end

      it "doesn't substitute if there is only {}" do

        dsub("le petit {renard}").should == "le petit {renard}"
      end

      it "substitutes at the end" do

        dsub("le petit ${renard}").should == "le petit goupil"
      end

      it "substitutes in the middle" do

        dsub("le petit ${renard} noir").should == "le petit goupil noir"
      end

      it "substitutes when there are two ${}" do

        dsub("le ${renard} et la ${cane}").should == "le goupil et la oie"
          # excuse my french
      end

      it "doesn't substitute when escaped \\\\${renard}" do

        dsub("le petit \\${renard} noir").should == "le petit \\${renard} noir"
      end

      it "leaves \\n untouched" do

        dsub("\n").should == "\n"
      end

      it "substitutes to a blank when there is no entry in the dict" do

        dsub("le petit ${chien} suisse").should == "le petit  suisse"
      end

      it "'inspects' arrays" do

        dsub("the ${customers}").should == 'the ["alice", "bob"]'
      end

      it "'inspects' hashes" do

        dsub("${table}").should == '{2011=>2, 2012=>7}'
      end
    end
  end

  #def test_0
  #  dotest " ${a${b}e} ", {}, "  "
  #  dotest " ${a{b}e} ", {}, "  "
  #  dotest "${a{b}e}", {}, ""
  #  dotest " \\${a{b}e} ", {}, " \\${a{b}e} "
  #  dotest "{a${b}c}", { "b" => 2 }, "{a2c}"
  #end
    # no need to integrate that for now

  context 'nested brackets' do

    let(:dict) do
      {
        'B' => 'b',
        'ab' => 'ok'
      }
    end

    describe '.dsub' do

      it 'substitutes successively' do

        dsub("${a${B}}").should == 'ok'
      end
    end
  end

  context 'dollar bracket double-quote' do

    let(:dict) do
      {
        'renard' => 'goupil'
      }
    end

    describe '.dsub' do

      it 'encloses in double-quotes when ${\'renard}' do

        dsub("${'renard}").should == '"goupil"'
      end

      it 'encloses in double-quotes when ${"renard}' do

        dsub('${"renard}').should == '"goupil"'
      end
    end
  end
end

