package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.google.common.collect.Maps;

public class ServiceInstanceState extends TaskConsumerState {

	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
		public static final String STOPPING_INSTANCE = "STOPPING_INSTANCE";
		public static final String INSTANCE_STOPPED = "INSTANCE_STOPPED";
		public static final String INSTANCE_UNREACHABLE = "INSTANCE_UNREACHABLE";
	}
	
	private String progress;
	private URI agentId;
	private URI serviceId;
	
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
    
	public String getProgress() {
		return progress;
	}
	
	public void setProgress(String progress) {
		this.progress = progress;
	}

	public URI getAgentId() {
		return agentId;
	}

	public void setAgentId(URI agentId) {
		this.agentId = agentId;
	}

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
