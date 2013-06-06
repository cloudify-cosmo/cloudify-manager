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

class PreparePlanParticipant < Ruote::Participant

  def on_workitem
    begin
      # raise 'dsl not set' unless workitem.fields.has_key? 'dsl'

      # prepare plan

      # any ruote workflows in the plan should be parsed
      plan = Hash.new

      machine = Hash[ 'id' => 'machine/1', 'properties' => Hash[ 'image' => 'aws34234234' ] ]
      machine['relationships'] = Array.new
      machine_init = "define machine_init\n  echo ' -> machine_init'\n"
      machine['workflows'] = Hash['init' => Ruote::RadialReader.read(machine_init)]

      database = Hash[ 'id' => 'database/1', 'properties' => Hash[ 'port' => '3306' ] ]
      database['relationships'] = Array[ Hash['type' => 'hosted_on', 'target_id' => 'machine/1'] ]
      database_init = "define database_init\n  echo ' -> database_init'\n"
      database['workflows'] = Hash['init' => Ruote::RadialReader.read(database_init)]

      nodes = Array[machine, database]

      plan['nodes'] = nodes

      workitem.fields['plan'] = plan

      reply

    rescue Exception => e
      $logger.debug('Exception caught on prepare_plan participant execution: {}', e)
      raise e
    end
  end

end
