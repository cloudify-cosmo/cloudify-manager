package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Set;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceOrchestratorState extends TaskExecutorState {

	private Set<URL> instances = Sets.newLinkedHashSet();
	private URL downloadUrl;

	public Iterable<URL> getInstanceIds() {
		return instances;
	}
	
	public void addInstanceId(URL executorId) {
		instances.add(executorId);
	}

	public URL getDownloadUrl() {
		return downloadUrl;
	}
	
	public void setDownloadUrl(URL downloadUrl) {
		this.downloadUrl = downloadUrl;
	}

}
