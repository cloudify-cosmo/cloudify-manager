package org.openspaces.servicegrid;

import java.util.List;
import java.util.Map;

import com.beust.jcommander.internal.Lists;
import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.collect.Maps;

public class TaskConsumerState {

	//Should serialize to List<URI> which is the taskid URIs
	private Task executingTask;
	private List<Task> tasksHistory = Lists.newArrayList();
	
	private Map<String, Object> properties = Maps.newLinkedHashMap();

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

	public List<Task> getTasksHistory() {
		return tasksHistory;
	}

	public void setTasksHistory(List<Task> tasksHistory) {
		this.tasksHistory = tasksHistory;
	}

	@JsonIgnore
	public void addTaskHistory(Task task) {
		tasksHistory.add(task);
	}
}