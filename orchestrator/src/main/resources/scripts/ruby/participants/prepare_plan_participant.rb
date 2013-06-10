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

java_import org.cloudifysource.cosmo.dsl.DSLProcessor
java_import org.cloudifysource.cosmo.dsl.PluginArtifactAwareDSLPostProcessor
require 'json'

class PreparePlanParticipant < Ruote::Participant

  def on_workitem
    begin
      raise 'dsl not set' unless workitem.params.has_key? 'dsl'

      raw_dsl = workitem.params['dsl']

      processed_dsl = DSLProcessor.process(raw_dsl, PluginArtifactAwareDSLPostProcessor.new)

      plan = JSON.parse(processed_dsl)

      plan['nodes'].each do |node|
        workflows = Hash.new
        node['workflows'].each { |key, value| workflows[key] = Ruote::RadialReader.read(value)  }
        node['workflows'] = workflows
      end

      workitem.fields['plan'] = plan

      reply

    rescue Exception => e
      $logger.debug('Exception caught on prepare_plan participant execution: {}', e)
      raise e
    end
  end

end
