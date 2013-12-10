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

require 'sinatra'
require 'json'
require 'parslet'
require_relative 'ruote/ruote_workflow_engine'

$ruote_service = RuoteWorkflowEngine.new(:test => settings.test?)


class RuoteServiceApp < Sinatra::Base

  configure do
    set :show_exceptions => false
    set :raise_errors => true
  end

  get '/', :provides => :json do
    content_type :json
    JSON.pretty_generate({:version => '1.0'})
  end

  get '/workflows', :provides => :json do
    content_type :json
    begin
      JSON.pretty_generate $ruote_service.get_workflows
    rescue Exception => e
      error_response e.message
    end
  end

  post '/workflows', :provides => :json do
    content_type :json
    begin
      req = self.parse_request_body(request)
      validation_message = nil

      unless req.has_key?(:radial)
        validation_message = 'Radial key is missing in request body'
      end

      fields = req[:fields] || {}
      if validation_message.nil? and not fields.class.eql?(Hash)
        validation_message = "Fields key value type is expected to be a hash/map but is #{fields.class.to_s}"
      end

      tags = req[:tags] || {}
      if validation_message.nil? and not tags.class.eql?(Hash)
        validation_message = "Tags key value type is expected to be a hash/map but is #{tags.class.to_s}"
      end

      if validation_message.nil?
        status 201
        JSON.pretty_generate $ruote_service.launch(req[:radial], fields, tags)
      else
        error_response validation_message, 400
      end
    rescue Parslet::ParseFailed => e
      error_response "Radial parsing failed: #{e.message}", 400
    rescue Exception => e
      error_response e.message
    end
  end

  get '/workflows/:id', :provides => :json do
    content_type :json
    begin
      wfid = params[:id]
      JSON.pretty_generate $ruote_service.get_workflow_state(wfid)
    rescue WorkflowDoesntExistError => e
      error_response e.message, 400
    rescue Exception => e
      error_response e.message
    end
  end

  not_found do
    status 404
    JSON.pretty_generate({:status => :error, :error => 'Not found'})
  end

  def parse_request_body(request)
    JSON.parse(request.body.read, :symbolize_names => true)
  end

  def error_response(message, status_code=500)
    status status_code
    JSON.pretty_generate({ :status => status_code, :message => message })
  end

end


