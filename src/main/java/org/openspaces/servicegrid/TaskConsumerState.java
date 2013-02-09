package org.openspaces.servicegrid;

import java.net.URI;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.google.common.collect.Maps;

public class TaskConsumerState {

	//Should serialize to List<URI> which is the taskid URIs
	private Task executingTask;

	private Map<String, Object> properties = Maps.newLinkedHashMap();

	private URI tasksHistory;
	
    @JsonAnySetter 
    public void setProperty(String key, Object value) {
      properties.put(key, value);
    }

    @JsonAnyGetter 
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