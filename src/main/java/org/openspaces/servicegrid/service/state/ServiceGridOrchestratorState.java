package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;

public class ServiceGridOrchestratorState extends TaskConsumerState {

	private ServiceGridDeploymentPlan deploymentPlan;
	private boolean deploymentPlanChanged;

	public ServiceGridDeploymentPlan getDeploymentPlan() {
		return deploymentPlan;
	}

	public void setDeploymentPlan(ServiceGridDeploymentPlan deploymentPlan) {
		this.deploymentPlan = deploymentPlan;
	}

	public boolean isDeploymentPlanChanged() {
		return deploymentPlanChanged;
	}

	public void setDeploymentPlanChanged(boolean deploymentPlanChanged) {
		this.deploymentPlanChanged = deploymentPlanChanged;
	}
	
	@JsonIgnore
	public Iterable<URI> getServiceInstanceIds(URI serviceId) {
		return deploymentPlan.getInstanceIdsByServiceId().get(serviceId);
	}

	@JsonIgnore
	public Iterable<URI> getAgentInstanceIds(URI agentId) {
		return deploymentPlan.getInstanceIdsByAgentId().get(agentId);
	}
	
	@JsonIgnore
	public List<ServiceConfig> getServices() {
		return deploymentPlan.getServices();
	}
	
	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		return deploymentPlan.getInstanceIdsByAgentId().keySet();
	}

	@JsonIgnore
	public URI getAgentIdOfServiceInstance(final URI instanceId) {
		Collection<Entry<URI, URI>> instanceIdByAgentId = deploymentPlan.getInstanceIdsByAgentId().entries();
		return Iterables.find(instanceIdByAgentId, new Predicate<Map.Entry<URI,URI>>() {

					@Override
					public boolean apply(Map.Entry<URI,URI> entry) {
						return instanceId.equals(entry.getValue());
					}
		}, null).getKey();
	}

}
