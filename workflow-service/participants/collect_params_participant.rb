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
require_relative '../utils/logs'

class CollectParamsParticipant < Ruote::Participant

  NAMES = 'names'
  OUTPUT_FIELD_NAME = 'to_f'

  def on_workitem
    begin
      raise "Missing 'names' parameter" unless workitem.params.has_key? NAMES
      raise "Missing 'to_f' parameter" unless workitem.params.has_key? OUTPUT_FIELD_NAME
      param_names = workitem.params[NAMES]
      output_field_name = workitem.params[OUTPUT_FIELD_NAME]
      result = {}
      param_names.each do |name|
        value = workitem.fields[name]
        result[name] = value unless value.nil?
      end
      log(:debug,
        "CollectParamsParticipant: names: [#{param_names}], to_f:[#{output_field_name}], result: [#{result}]",
        {
          :workitem => workitem,
          :arguments => {
            :param_names => param_names,
            :output_field_name => output_field_name,
            :result => result
          }
        })
      workitem.fields[output_field_name] = result
      reply
    rescue => e
      log_exception(workitem, e, 'collect_params')
      flunk(workitem, e)
    end
  end

end