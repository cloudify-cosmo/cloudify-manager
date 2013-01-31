package org.openspaces.servicegrid;

import java.net.URI;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

public class TaskConsumerState {

	//Should serialize to List<URI> which is the taskid URIs
	private List<URI> executingTasks = Lists.newArrayList();
	private List<URI> completedTasks = Lists.newArrayList();
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

	public void executeTask(URI taskId) {
		Preconditions.checkNotNull(taskId);
		getExecutingTasks().add(taskId);
	}
	
	public void completeExecutingTask(URI taskId) {
		boolean remove = getExecutingTasks().remove(taskId);
		Preconditions.checkState(remove,"task " + taskId + " is not executing");
		getCompletedTasks().add(taskId);
	}

	public List<URI> getExecutingTasks() {
		return executingTasks;
	}

	public void setExecutingTasks(List<URI> executingTasks) {
		this.executingTasks = executingTasks;
	}

	public List<URI> getCompletedTasks() {
		return completedTasks;
	}

	public void setCompletedTasks(List<URI> completedTasks) {
		this.completedTasks = completedTasks;
	}
}
