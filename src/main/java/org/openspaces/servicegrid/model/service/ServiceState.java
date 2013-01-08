package org.openspaces.servicegrid.model.service;

import java.net.URI;
import java.util.Map;

import org.codehaus.jackson.annotate.JsonIgnore;
import org.openspaces.servicegrid.ServiceConfig;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;

public class ServiceState extends TaskExecutorState {
	
	private Map<URI,URI> instanceIdToAgentIdMapping = Maps.newLinkedHashMap();
	
	private ServiceConfig serviceConfig;

	@JsonIgnore
	public Iterable<URI> getInstancesIds() {
		return Iterables.unmodifiableIterable(getInstanceIdToAgentIdMapping().keySet());
	}
	
	@JsonIgnore
	public URI getAgentIdOfInstance(URI instanceId) {
		return getInstanceIdToAgentIdMapping().get(instanceId);
	}
	
	@JsonIgnore
	public void addInstanceId(URI instanceId, URI agentId) {
		getInstanceIdToAgentIdMapping().put(instanceId, agentId);
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public Map<URI,URI> getInstanceIdToAgentIdMapping() {
		return instanceIdToAgentIdMapping;
	}

	public void setInstanceIdToAgentIdMapping(
			Map<URI,URI> instanceIdToAgentIdMapping) {
		this.instanceIdToAgentIdMapping = instanceIdToAgentIdMapping;
	}
}
