#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

require_relative '../amqp/amqp_client'


def get_logging_level(level_str)
  return level_str.to_s.downcase.to_sym
end

LOG_LEVEL = get_logging_level(ENV['WF_SERVICE_LOG_LEVEL'] || 'info')

LEVELS = {
    :debug => 3,
    :info => 2,
    :warning => 1,
    :error => 0,
}

def log(level, message, context={})
  begin
    if level != :off and LEVELS[level] <= LEVELS[LOG_LEVEL]
      AMQPClient::publish_log(level, message, context)
      $logger.debug(message)
    end
  rescue Exception => e
    $logger.debug("Error publishing log message: #{e.message}")
  end
end

class StubLogger
  def initialize; end
  def debug(message, *args)
    #message = "#{message}, #{args}\n"
    #File.open('/home/dan/work/logs/out.log', 'a') { |f|
    #  f.write()
    #}
    #puts message
  end
end