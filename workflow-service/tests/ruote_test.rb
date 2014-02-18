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
require 'time'
require '../ruote/ruote_workflow_engine'
require 'tmpdir'
require 'fileutils'

class RuoteTest < Test::Unit::TestCase

  def setup
    @ruote = RuoteWorkflowEngine.new(:test => true)
  end

  def teardown
    @ruote.close if @ruote
  end

  def test_workflow_execution
    radial = %/
define wf
  echo 'hello world'
/
    wf = @ruote.launch(radial)
    assert_equal :pending, wf.state
  end

  def test_workflow_execution_with_tags
    radial = %/
define wf
  echo 'hello world'
/
    wf = @ruote.launch(radial, {}, { :blueprint => 'some_blueprint' })
    assert_equal :pending, wf.state
  end

  def test_workflow_state
    radial = %/
define wf
  echo 'waiting for 3 seconds...'
  wait for: '3s'
  echo 'done!'
/
    wf = @ruote.launch(radial)
    assert_equal :pending, wf.state
    wf = @ruote.get_workflow_state(wf.id)
    assert_equal wf.state, :pending
    wait_for_workflow_state(wf.id, :launched, 5)
    wait_for_workflow_state(wf.id, :terminated, 5)
  end

  def wait_for_workflow_state(wfid, state, timeout=5)
    deadline = Time.now + timeout
    state_ok = false
    while not state_ok and Time.now < deadline
      begin
        wf = @ruote.get_workflow_state(wfid)
        assert_equal state, wf.state
        state_ok = true
      rescue Exception
        sleep 0.5
      end
    end
    unless state_ok
      wf = @ruote.get_workflow_state(wfid)
      assert_equal state, wf.state
    end
  end

  # This test is used for verifying there's no problem with Ruote's on_msg
  # mechanism for monitoring workflows activity since its also relevant for
  # sub-workflows.
  def test_sub_workflow
    radial = %(
define wf
  echo 'parent workflow echo'
  sub_wf on_error: 'handler'

  define sub_wf
    log
    echo 'this is a sub workflow echo'
    sleep for: '2s'

  define handler
    echo 'handler invoked'
    echo '${__error__}'
    log message: 'hello!'
    echo 'handler invoked and set'

)
    wf = @ruote.launch(radial)
    assert_equal :pending, wf.state
    wait_for_workflow_state(wf.id, :terminated, 5)
  end

  def test_get_workflows
    assert_equal 0, @ruote.get_workflows.size
    radial = %/
define wf
  echo 'hello world'
/
    wf = @ruote.launch(radial)
    assert_equal 1, @ruote.get_workflows.size
    wf_state = @ruote.get_workflows[0]
    assert_equal wf.id, wf_state.id
    @ruote.launch(radial)
    assert_equal 2, @ruote.get_workflows.size
  end

end