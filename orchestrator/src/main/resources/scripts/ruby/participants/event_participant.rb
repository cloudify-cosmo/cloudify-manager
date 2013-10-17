#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

require_relative '../exception_logger'

class EventParticipant < Ruote::Participant

  NODE = 'node'
  EVENT = 'event'

  def do_not_thread
    true
  end

  def on_workitem
    begin

      raise 'event not set' unless workitem.params.has_key? EVENT
      event = workitem.params[EVENT]

      EventParticipant.log_event(event, workitem)

      reply(workitem)

    rescue => e
      log_exception(e, 'event')
      flunk(workitem, e)
    end
  end

  def self.log_event(event, workitem=nil)
    if workitem != nil
      sub_workflow_name = workitem.sub_wf_name
      workflow_name = workitem.wf_name
      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        parts = node['id'].split('.')
        event['node'] = parts[1]
        event['app'] = parts[0]
      end
      event['workflow_name'] = workflow_name
      event['workflow_id'] = workitem.wfid
      event['type'] = 'workflow'
      json_event = JSON.pretty_generate(event)
      if sub_workflow_name == workflow_name
        # no need to print sub workflow if there is none
        $user_logger.debug("[#{workflow_name}]\n#{json_event}")
      else
        $user_logger.debug("[#{workflow_name}.#{sub_workflow_name}]\n#{json_event}")
      end
    else
      $user_logger.debug("[workflow]\n#{json_event}")
    end

  end

end