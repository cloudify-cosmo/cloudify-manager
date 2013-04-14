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

#####
# Ruby script for running ruote workflows.
# Workflow is injected to the script using the $workflow variable.
#
# Additionally, a ruote participant for running java code is included.
#
# author: Idan Moyal
# since: 0.1
#

require 'rubygems'
require 'ruote'
require 'java'

class JavaClassParticipant < Ruote::Participant
  def on_workitem
    puts '--- JavaClassParticipant invocation:'

    puts 'workitem.fields:'
    puts workitem.fields

    java_class_name = workitem.params['class']
    java_participant = eval("#{java_class_name}.new")
    java_participant.execute()

    puts '--- DONE.'
    puts "\n"

    reply
  end
end

engine = Ruote::Engine.new(Ruote::Worker.new(Ruote::HashStorage.new))
engine.register_participant 'java', JavaClassParticipant

radial_workflow = Ruote::RadialReader.read($workflow)

wfid = engine.launch(radial_workflow, 'appliances' => $appliances)
engine.wait_for(wfid)
