package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonUnwrapped;
import com.google.common.base.Preconditions;

public class ServiceState extends TaskConsumerState {
	
	public static class Progress{
		public static final String INSTALLING_SERVICE = "INSTALLING_SERVICE";
		public static final String SERVICE_INSTALLED = "SERVICE_INSTALLED";
		public static final String UNINSTALLING_SERVICE = "UNINSTALLING_SERVICE";
		public static final String SERVICE_UNINSTALLED = "SERVICE_UNINSTALLED";
	}

	private List<URI> instanceIds;
	
	private ServiceConfig serviceConfig;

	private String progress;
	
	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
	@JsonUnwrapped
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public List<URI> getInstanceIds() {
		return instanceIds;
	}
	
	public void setInstanceIds(List<URI> instanceIds) {
		this.instanceIds = instanceIds;
	}

	public void setProgress(String progress) {
		this.progress = progress;
	}
	
	public String getProgress() {
		return progress;
	}

	@JsonIgnore
	public void removeInstance(URI instanceId) {
		boolean removed = instanceIds.remove(instanceId);
		Preconditions.checkArgument(removed, "Cannot remove instance %s", instanceId);
	}
}
