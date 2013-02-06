package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;

import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;

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
	
	public static URI toTasksURI(final URI taskConsumerId) {
		try {
			return new URI(taskConsumerId.toString() + "tasks/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
		
	public static URI newTasksId(URI tasks, Integer start, Integer end) {
		Preconditions.checkArgument(start != null || end != null);
		StringBuilder uri = new StringBuilder();
		uri.append(tasks.toString());
		if (start != null) {
			uri.append(start);
		}
		uri.append("..");
		if (end != null) {
			uri.append(end);
		}
		try {
			return new URI(uri.toString());
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	public static URI newTaskId(URI postNewTask, int taskIndex) {
		StringBuilder uri = new StringBuilder();
		uri.append(postNewTask.toString()).append(taskIndex);
		try {
			return new URI(uri.toString());
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	public static URI toTasksHistoryId(URI stateId) {
		return StreamUtils.newURI(stateId.toString()+"_tasks_history");
	}
}
