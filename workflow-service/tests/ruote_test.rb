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
require_relative '../ruote/ruote_workflow_engine'
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
    radial = %/
define wf
  echo 'parent workflow echo'
  do_that


  define do_that
    set 'v:yoyo': '$f:idan'
    yoyo
    echo '${result}'

  define sub_wf
    echo 'this is a sub workflow echo'
    sleep for: '1s'
    log message: 'yikes'
    set 'f:result': '$hello'
/
    aaa = %/
define my_wf
  sub_wf
/
    fields = { "idan" => aaa }
    wf = @ruote.launch(radial, fields)
    assert_equal :pending, wf.state
    wait_for_workflow_state(wf.id, :terminated, 10)
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


  def test_radial
    radial1 = %(define host_start
    execute_operation operation: 'cloudify.interfaces.lifecycle.start'

    execute_operation operation: 'cloudify.interfaces.detection.get_state', to_f: 'is_started'
    event event: { "stage" => "is_started = ${f:is_started}" }

    sequence if: '${node.properties.install_agent} == true'
        event event: { "stage" => "Verifying host has started" }
        state action: 'wait', node_id: '${node.id}', reachable: 'true'
        log message: 'installing agent on host: ${node.id}'
        event event: { "stage" => "Installing worker" }
        execute_operation operation: 'cloudify.interfaces.worker_installer.install'
        execute_operation operation: 'cloudify.interfaces.worker_installer.start'
        event event: { "stage" => "Installing plugins" }
        log message: 'installing plugins on host: ${node.id} - plugins: ${node.plugins_to_install}'
        iterator on: '$node.plugins_to_install', to_v: 'plugin'
            log message: 'installing plugin: ${v:plugin.name} on host: ${node.id}'
            event event: { "stage" => "Installing plugin ${v:plugin.name}" }
            execute_operation operation: 'cloudify.interfaces.plugin_installer.install', params: {
                plugin: {
                    name: '${v:plugin.name}',
                    url: '${v:plugin.url}'
                 }
            }
            log message: 'successfully installed plugin: ${v:plugin.name} on host: ${node.id}'
        log message: 'restarting worker on host: ${node.id}'
        execute_operation operation: 'cloudify.interfaces.worker_installer.restart'
        execute_operation operation: 'cloudify.interfaces.kv_store.put', params: {
            key: "agent plugins installed",
            value: true
        }
)

    radial2 = %(#{}
define host_start
    execute_operation operation: 'cloudify.interfaces.lifecycle.start'

    execute_operation operation: 'cloudify.interfaces.detection.get_state', to_f: 'is_started'
    event event: { "stage" => "is_started = ${f:is_started}" }

    sequence if: '${node.properties.install_agent} == true'
        event event: { "stage" => "Verifying host has started" }
        state action: 'wait', node_id: '${node.id}', reachable: 'true'
        log message: 'installing agent on host: ${node.id}'
        event event: { "stage" => "Installing worker" }
        execute_operation operation: 'cloudify.interfaces.worker_installer.install'
        execute_operation operation: 'cloudify.interfaces.worker_installer.start'
        event event: { "stage" => "Installing plugins" }
        log message: 'installing plugins on host: ${node.id} - plugins: ${node.plugins_to_install}'
        iterator on: '$node.plugins_to_install', to_v: 'plugin'
            log message: 'installing plugin: ${v:plugin.name} on host: ${node.id}'
            event event: { "stage" => "Installing plugin ${v:plugin.name}" }
            execute_operation operation: 'cloudify.interfaces.plugin_installer.install', params: {
                plugin: {
                    name: '${v:plugin.name}',
                    url: '${v:plugin.url}'
                 }
            }
            log message: 'successfully installed plugin: ${v:plugin.name} on host: ${node.id}'
        log message: 'restarting worker on host: ${node.id}'
        execute_operation operation: 'cloudify.interfaces.worker_installer.restart'
        execute_operation operation: 'cloudify.interfaces.kv_store.put', params: {
            key: "agent plugins installed",
            value: true
        }
)

    result1 = Ruote::RadialReader.read(radial1)
    result2 = Ruote::RadialReader.read(radial2)
    puts result1 == result2


  end

end