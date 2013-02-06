package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.streams.StreamUtils;

public class ServiceUtils {
	
	public static AgentState getAgentState(
			final StateReader stateReader, 
			final URI agentId) {
		EtagState<AgentState> etagState = stateReader.get(agentId, AgentState.class);
		return etagState == null ? null : etagState.getState();
	}

	public static ServiceState getServiceState(
			final StateReader stateReader,
			final URI serviceId) {
		EtagState<ServiceState> etagState = stateReader.get(serviceId, ServiceState.class);
		return etagState == null ? null : etagState.getState();
	}
	
	public static ServiceInstanceState getServiceInstanceState(
			final StateReader stateReader, 
			final URI instanceId) {
		EtagState<ServiceInstanceState> etagState = stateReader.get(instanceId, ServiceInstanceState.class);
		return etagState == null ? null : etagState.getState();
	}
	
	public static URI toTasksHistoryId(URI stateId) {
		return StreamUtils.newURI(stateId.toString()+"_tasks_history");
	}
}
