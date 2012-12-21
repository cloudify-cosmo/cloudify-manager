package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Set;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceOrchestratorState extends TaskExecutorState {

	private ServiceConfig config;
	
	private Set<URL> instances = Sets.newLinkedHashSet();
	
	public ServiceConfig getConfig() {
		return config;
	}
	
	public void setConfig(ServiceConfig config) {
		this.config = config;
	}

	public Iterable<URL> getInstanceIds() {
		return instances;
	}
	
	public void addInstanceId(URL executorId) {
		instances.add(executorId);
	}
}
