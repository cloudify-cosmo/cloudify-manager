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

require '../app'
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
    assert_equal 'ruote-rest-api', last_response.body
  end

  def test_no_workflows
    get '/workflows'
    workflows = JSON.parse(last_response.body)['workflows']
    assert_empty workflows
  end

  def test_launch
    radial = %/
define wf
  echo '1..2..3..'
/
    post '/workflows', {
        :radial => radial
    }.to_json
    assert_equal 200, last_response.status
    res = JSON.parse(last_response.body, :symbolize_names => true)
    assert_equal 'workflow_state', res[:type]
    assert_equal 'pending', res[:state]
    assert_includes res.keys, :id, :created
    assert_equal false, res[:id].empty?
    assert_equal false, res[:created].empty?

  end

  def test_get_workflow_state
    radial = %/
define wf
  echo 'hello!'
/
    post '/workflows', {
        :radial => radial
    }.to_json
    assert_equal 200, last_response.status
    res = JSON.parse(last_response.body, :symbolize_names => true)
    wfid = res[:id]
    get "/workflows/#{wfid}"
    res = JSON.parse(last_response.body, :symbolize_names => true)
    assert_equal 'workflow_state', res[:type]
    assert_equal wfid, res[:id]
    assert_include %w(pending launched terminated), res[:state]
  end

  #def test_launch_wrong_fields_type
  #
  #end

end