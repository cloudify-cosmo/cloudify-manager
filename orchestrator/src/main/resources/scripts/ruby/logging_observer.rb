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

require 'json'

class LoggingObserver

  def initialize(context)
    @context = context
  end

  def on_msg(msg)
    begin
      $logger.debug('[event] ' + JSON.generate(msg))
    rescue => e
      backtrace = e.backtrace if e.respond_to?(:backtrace)
      $logger.debug("error logging event: #{e.to_s} / #{backtrace}")
    end
  end

end
