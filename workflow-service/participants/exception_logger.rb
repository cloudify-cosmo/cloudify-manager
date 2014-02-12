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


require_relative '../utils/logs'

def log_exception(workitem, exception, participant_name='ruote', raise_exception=false)
  backtrace = nil?
  if exception.kind_of? Exception
    backtrace = exception.backtrace if exception.respond_to?(:backtrace)
  end
  log(:error, "Exception caught in '#{participant_name}' participant [exception=#{exception}, stacktrace=#{backtrace}]",
    {
      :workitem => workitem,
      :arguments => {
          :participant_name => participant_name,
          :exception => exception,
          :stacktrace => backtrace
      }
    })
  raise exception if raise_exception
end

