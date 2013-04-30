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
    $logger.debug('--- JavaClassParticipant invocation:')
    $logger.debug('workitem.fields: {}', workitem.fields)

    begin
      java_class_name = workitem.params['class']
      java_participant = eval("#{java_class_name}.new")
      java_participant.execute(workitem.fields)
    rescue Exception => e
      $logger.debug('Exception: {}', e.message)
      $logger.debug('Trace: {}', e.backtrace.inspect)
    end

    $logger.debug('--- DONE.')

    reply
  end
end