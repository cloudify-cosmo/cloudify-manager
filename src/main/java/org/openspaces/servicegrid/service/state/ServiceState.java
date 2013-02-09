package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
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
	
	//@JsonUnwrapped
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
	
	/**
	 * Use isProgress(x or y or z) instead. 
	 * This is to encourage using the pattern of positive progress checks such as "isProgress(y)" 
	 * instead of negative progress checks such as (!getProgress().equals(x)) 
	 */
	@Deprecated
	public String getProgress() {
		return progress;
	}

	/**
	 * @return true if {@code #getProgress()} matches any of the specified options.
	 */
	public boolean isProgress(String ... expectedProgresses) {
		for (String expectedProgress : expectedProgresses) {
			if (progress != null && progress.equals(expectedProgress)) {
				return true;
			}
		}
		return false;
	}


	@JsonIgnore
	public void removeInstance(URI instanceId) {
		boolean removed = instanceIds.remove(instanceId);
		Preconditions.checkArgument(removed, "Cannot remove instance %s", instanceId);
	}
}
