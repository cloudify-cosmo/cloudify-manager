package org.openspaces.servicegrid.service.state;

import java.net.URI;

import org.openspaces.servicegrid.TaskConsumerState;

public class ServiceInstanceState extends TaskConsumerState {

	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
		public static final String STOPPING_INSTANCE = "STOPPING_INSTANCE";
		public static final String INSTANCE_STOPPED = "INSTANCE_STOPPED";
		public static final String UNINSTALLING_INSTANCE = "UNINSTALLING_INSTANCE";
		public static final String INSTANCE_UNINSTALLED = "INSTANCE_UNINSTALLED";
		public static final String INSTANCE_UNREACHABLE = "INSTANCE_UNREACHABLE";
	}
	
	private String progress;
	private URI agentId;
	private URI serviceId;
	
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
}
