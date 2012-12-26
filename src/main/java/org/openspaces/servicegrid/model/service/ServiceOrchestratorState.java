package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Set;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceOrchestratorState extends TaskExecutorState {

	private Set<URL> instances = Sets.newLinkedHashSet();
	private Set<URL> agents = Sets.newLinkedHashSet();
	private String displayName;

	public Iterable<URL> getInstanceIds() {
		return instances;
	}
	
	public void addInstanceId(URL executorId) {
		instances.add(executorId);
	}

	public String getDisplayName() {
		return displayName;
	}
	
	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}

	public Set<URL> getAgents() {
		return agents;
	}

	public void setAgents(Set<URL> agents) {
		this.agents = agents;
	}

}
