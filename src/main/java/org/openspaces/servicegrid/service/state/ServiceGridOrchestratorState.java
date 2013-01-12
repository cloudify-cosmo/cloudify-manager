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

	private ServiceGridFloorPlan floorPlan;
	private boolean floorPlanChanged;

	public ServiceGridFloorPlan getFloorPlan() {
		return floorPlan;
	}

	public void setFloorPlan(ServiceGridFloorPlan floorPlan) {
		this.floorPlan = floorPlan;
	}

	public boolean isFloorPlanChanged() {
		return floorPlanChanged;
	}

	public void setFloorPlanChanged(boolean floorPlanChanged) {
		this.floorPlanChanged = floorPlanChanged;
	}
	
	@JsonIgnore
	public Iterable<URI> getServiceInstanceIds(URI serviceId) {
		return floorPlan.getInstanceIdsByServiceId().get(serviceId);
	}

	@JsonIgnore
	public Iterable<URI> getAgentInstanceIds(URI agentId) {
		return floorPlan.getInstanceIdsByAgentId().get(agentId);
	}
	
	@JsonIgnore
	public List<ServiceConfig> getServices() {
		return floorPlan.getServices();
	}
	
	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		return floorPlan.getInstanceIdsByAgentId().keySet();
	}

	@JsonIgnore
	public URI getAgentIdOfServiceInstance(final URI instanceId) {
		Collection<Entry<URI, URI>> instanceIdByAgentId = floorPlan.getInstanceIdsByAgentId().entries();
		return Iterables.find(instanceIdByAgentId, new Predicate<Map.Entry<URI,URI>>() {

					@Override
					public boolean apply(Map.Entry<URI,URI> entry) {
						return instanceId.equals(entry.getValue());
					}
		}, null).getKey();
	}

}
