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

class PrepareOperationParticipant < Ruote::Participant

  NODE = 'node'
  OPERATION = 'operation'
  OPERATIONS = 'operations'
  TARGET = 'target'

  def on_workitem
    begin
      raise "#{NODE} field not set" unless workitem.fields.has_key? NODE
      raise "#{OPERATION} parameter not set" unless workitem.params.has_key? OPERATION

      node = workitem.fields[NODE]
      operation = workitem.params[OPERATION]

      operations = node[OPERATIONS]
      raise "Node has no operations: #{node}" unless operations != nil
      raise "No such operation '#{operation}' for node: #{node}" unless operations.has_key? operation

      workitem.fields[TARGET] = operations[operation]
      # operation can have the interface name as its prefix: 'control.start' or just 'start'
      workitem.fields[OPERATION] = operation.split('.')[-1]

      reply
    rescue Exception => e
      $logger.debug('Exception caught on prepare_operation participant execution: {}', e)
      raise e
    end
  end

end
