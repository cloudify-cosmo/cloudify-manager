package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Map;

import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Maps;


public class AggregatedServiceState {

	private ServiceConfig config;
	private Map<URL,ServiceInstanceState> instances = Maps.newLinkedHashMap();

	public void setServiceConfig(ServiceConfig config) {
		this.config = config;	
	}

	public void addInstance(URL instanceId, ServiceInstanceState instanceState) {
		instances.put(instanceId, instanceState);
	}

	public ServiceConfig getConfig() {
		return config;
	}

	public Map<URL,ServiceInstanceState> getInstances() {
		return ImmutableMap.<URL, ServiceInstanceState>builder().putAll(instances).build();
	}
	
	 
}
