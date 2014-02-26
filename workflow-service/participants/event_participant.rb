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

require_relative 'exception_logger'
require_relative '../amqp/amqp_client'
require_relative '../utils/events'
require 'time'


class EventParticipant < Ruote::Participant

  NODE = 'node'
  EVENT = 'event'
  PLAN = 'plan'
  DEPLOYMENT_ID = 'deployment_id'

  def do_not_thread
    true
  end

  def on_workitem
    begin

      raise 'event not set' unless workitem.params.has_key? EVENT
      event = workitem.params[EVENT]

      event(:workflow_stage, {
          :workitem => workitem,
          :message => event['stage']
      })

      reply(workitem)

    rescue => e
      log_exception(workitem, e, 'event')
      flunk(workitem, e)
    end
  end

end