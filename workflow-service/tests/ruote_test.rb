#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

require 'test/unit'
require 'json'
require '../ruote/ruote_workflow_engine'

class RuoteTest < Test::Unit::TestCase

  def setup
    @ruote = RuoteWorkflowEngine.new(:testing => true)
  end

  def teardown
    @ruote.close
  end

  def test_workflow_execution
    radial = %/
define wf
  echo 'hello world'
/
    wf = @ruote.launch(radial)
    assert_equal wf.state, :pending
  end

end