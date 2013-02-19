/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.openspaces.servicegrid;

import java.net.URI;
import java.util.Map;

import com.google.common.collect.Maps;

public class TaskConsumerState {

	//Should serialize to List<URI> which is the taskid URIs
	private Task executingTask;

	private Map<String, Object> properties = Maps.newLinkedHashMap();

	private URI tasksHistory;
	
    //@JsonAnySetter 
    public void setProperty(String key, Object value) {
      properties.put(key, value);
    }

    //@JsonAnyGetter 
    public Map<String,Object> getProperties() {
      return properties;
    }
    
    public Object getProperty(String key) {
    	return properties.get(key);
    }

	public Task getExecutingTask() {
		return executingTask;
	}

	public void setExecutingTask(final Task executingTask) {
		this.executingTask = executingTask;
	}

	public URI getTasksHistory() {
		return tasksHistory;
	}

	public void setTasksHistory(URI tasksHistory) {
		this.tasksHistory = tasksHistory;
	}
}
