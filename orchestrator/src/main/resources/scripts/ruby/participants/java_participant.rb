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

class JavaClassParticipant < Ruote::Participant
  def on_workitem
    puts '--- JavaClassParticipant invocation:'

    puts 'workitem.fields:'
    puts workitem.fields

    begin
      java_class_name = workitem.params['class']
      java_participant = eval("#{java_class_name}.new")
      java_participant.execute(workitem.fields)
    rescue Exception => e
      puts "Exception: #{e.message}"
      puts "Trace: #{e.backtrace.inspect}"
    end

    puts '--- DONE.'
    puts "\n"

    reply
  end
end