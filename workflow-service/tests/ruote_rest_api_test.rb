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

ENV['RACK_ENV'] = 'test'

require_relative '../app'
require 'test/unit'
require 'rack/test'
require 'json'

class RuoteRestApiTest < Test::Unit::TestCase
  include Rack::Test::Methods

  def app
    RuoteServiceApp.new
  end

  def test_root
    get '/'
    assert_response_status 200
  end

  def test_launch
    radial = %/
define wf
  echo 'hello!'
/
    post '/workflows', { :radial => radial }.to_json
    assert_response_status 201
    res = JSON.parse(last_response.body, :symbolize_names => true)
    assert_equal 'pending', res[:state]
    assert_includes res.keys, :id, :created
    assert_equal false, res[:id].empty?
    assert_equal false, res[:created].empty?
  end

  def test_radial_wrong_syntax
    radial = 'this cant be working...'
    begin
      post '/workflows', { :radial => radial }.to_json
      assert_fail_assertion 'expected exception'
    rescue
      assert_response_status 400
    end
  end

  def test_launch_fields
    radial = %/
define wf
  echo '$key'
/
    fields = { :key => 'value' }
    post '/workflows', { :radial => radial, :fields => fields }.to_json
    res = JSON.parse(last_response.body, :symbolize_names => true)
    wait_for_workflow_state(res[:id], :terminated)
  end

  def test_terminate
    radial = %/
define wf
  echo 'this is nice'
  sleep '100s'
/
    post '/workflows', { :radial => radial }.to_json
    res = parsed_response
    wait_for_workflow_state(res[:id], :launched)
    post "/workflows/#{res[:id]}", { :action => 'cancel' }.to_json
    assert_response_status 201
    wait_for_workflow_state(res[:id], :terminated)
  end

  def test_terminate_no_action
    radial = %/
define wf
  echo 'this is nice'
  sleep '100s'
/
    post '/workflows', { :radial => radial }.to_json
    res = parsed_response
    wait_for_workflow_state(res[:id], :launched)
    post "/workflows/#{res[:id]}", {}.to_json
    assert_response_status 400
  end

  def test_terminate_invalid_action
    radial = %/
define wf
  echo 'this is nice'
  sleep '100s'
/
    post '/workflows', { :radial => radial }.to_json
    res = parsed_response
    wait_for_workflow_state(res[:id], :launched)
    post "/workflows/#{res[:id]}", { :action => 'bad_action' }.to_json
    assert_response_status 400
  end

  def test_terminate_wf_not_exists
    post '/workflows/does-not-exist', { :action => 'cancel' }.to_json
    assert_response_status 400
  end

  def test_launch_tags
    radial = %/
define wf
  echo 'tags!'
/
    tags = { 'blueprint' => 'some_blueprint' }
    post '/workflows', { :radial => radial, :tags => tags }.to_json
    res = JSON.parse(last_response.body, :symbolize_names => true)
    wait_for_workflow_state(res[:id], :terminated)
  end

  def test_launch_illegal_tags
    radial = %/
define wf
  echo '$key'
/
    begin
      post '/workflows', { :radial => radial, :tags => 'illegal value' }.to_json
      assert_fail_assertion 'expected exception'
    rescue
      assert_response_status 400
    end
  end

  def test_launch_wrong_fields_type
    radial = %/
define wf
  echo '$key'
/
    fields = [ :key => 'value' ]
    begin
      post '/workflows', { :radial => radial, :fields => fields }.to_json
      assert_fail_assertion 'expected exception'
    rescue
      assert_response_status 400
    end
  end

  def test_get_workflows_states
    radial1 = %/
define wf1
  echo 'hello1!'
/
    post '/workflows', { :radial => radial1 }.to_json
    assert_equal 201, last_response.status
    wfid1 = parsed_response[:id]
    radial2 = %/
  define wf2
    echo 'hello2!'
  /
    post '/workflows', { :radial => radial2 }.to_json
    assert_equal 201, last_response.status
    wfid2 = parsed_response[:id]
    post "/states", { :workflows_ids => [wfid1, wfid2]}.to_json    
    assert_equal wfid1, parsed_response[0][:id]
    assert_equal wfid2, parsed_response[1][:id]
    assert_include %w(pending launched terminated), parsed_response[0][:state]
    assert_include %w(pending launched terminated), parsed_response[1][:state]
  end

  def test_get_workflows_states_nonexistent_workflow
    radial = %/
define wf
  echo 'hello!'
/
    post '/workflows', { :radial => radial }.to_json
    assert_equal 201, last_response.status
    wfid = parsed_response[:id]

    #querying for one existing id and one nonexistent id
    begin
      post "/states", { :workflows_ids => [wfid, 'woohoo']}.to_json
      assert_fail_assertion 'expected exception'
    rescue
      assert_response_status 400
    end
  end

  def test_get_workflow_state
    radial = %/
define wf
  echo 'hello!'
/
    post '/workflows', { :radial => radial }.to_json
    assert_equal 201, last_response.status
    wfid = parsed_response[:id]
    get "/workflows/#{wfid}"
    assert_equal wfid, parsed_response[:id]
    assert_include %w(pending launched terminated), parsed_response[:state]
  end  

  def test_workflow_not_exists
    wfid = 'woohoo'
    begin
      get "/workflows/#{wfid}"
      assert_fail_assertion 'expected exception'
    rescue
      assert_response_status 400
    end
  end

  def wait_for_workflow_state(wfid, state, timeout=10)
    deadline = Time.now + timeout
    state_ok = false
    res = nil
    while not state_ok and Time.now < deadline
      begin
        get "/workflows/#{wfid}"
        res = JSON.parse(last_response.body, :symbolize_names => true)
        assert_equal state.to_s, res[:state]
        state_ok = true
      rescue Exception
        sleep 0.5
      end
    end
    unless state_ok
      get "/workflows/#{wfid}"
      res = JSON.parse(last_response.body, :symbolize_names => true)
      puts "res: #{res[:state]}"
      assert_equal state.to_s, res[:state]
    end
    res
  end

  def test_get_workflows
    radial = %/
define wf
  echo 'hello!'
/
    post '/workflows', { :radial => radial }.to_json
    get '/workflows'
    assert_response_status 200
    assert parsed_response.size > 0
  end

  def test_not_found
    get '/woo'
    assert_response_status 404
  end

  def assert_response_status(expected_status)
    assert_equal expected_status, last_response.status
  end

  def parsed_response
    JSON.parse(last_response.body, :symbolize_names => true)
  end

end