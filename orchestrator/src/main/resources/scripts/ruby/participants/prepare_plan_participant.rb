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
      raise 'dsl not set' unless workitem.fields.has_key? 'dsl'

    rescue Exception => e
      $logger.debug('Exception caught on prepare_plan participant execution: {}', e)
      remove_listener
      raise e
    end
  end

end
