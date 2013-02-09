package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.net.URISyntaxException;

import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.TaskWriter;
import org.openspaces.servicegrid.kvstore.KVStoreServer;
import org.openspaces.servicegrid.service.ServiceGridCapacityPlanner;
import org.openspaces.servicegrid.service.ServiceGridCapacityPlannerParameter;
import org.openspaces.servicegrid.service.ServiceGridDeploymentPlanner;
import org.openspaces.servicegrid.service.ServiceGridDeploymentPlannerParameter;
import org.openspaces.servicegrid.service.ServiceGridOrchestrator;
import org.openspaces.servicegrid.service.ServiceGridOrchestratorParameter;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.google.common.base.Throwables;

public class MockManagement {

	private static final int STATE_SERVER_PORT = 8080;
	private final URI orchestratorId;
	private final URI deploymentPlannerId;
	private final URI capacityPlannerId;
	private final URI machineProvisionerId;
	private final MockState state;
	private final MockTaskBroker taskBroker;
	private final CurrentTimeProvider timeProvider;
	private final TaskConsumerRegistrar taskConsumerRegistrar;
	private final MockTaskBroker persistentTaskBroker;
	private final KVStoreServer stateServer;
	
	public MockManagement(TaskConsumerRegistrar taskConsumerRegistrar, CurrentTimeProvider timeProvider)  {
		this.taskConsumerRegistrar = taskConsumerRegistrar;
		this.timeProvider = timeProvider;
		try {
			orchestratorId = new URI("http://localhost/services/orchestrator/");
			deploymentPlannerId = new URI("http://localhost/services/deployment_planner/");
			capacityPlannerId = new URI("http://localhost/services/capacity_planner/");
			machineProvisionerId = new URI("http://localhost/services/provisioner/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
		state = new MockState();
		state.setLoggingEnabled(true);
		taskBroker = new MockTaskBroker();
		taskBroker.setLoggingEnabled(false);
		persistentTaskBroker = new MockTaskBroker();
		stateServer = new KVStoreServer();
		stateServer.start(STATE_SERVER_PORT);
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public TaskReader getTaskReader() {
		return taskBroker;
	}

	public TaskWriter getTaskWriter() {
		return taskBroker;
	}
	
	public StateReader getStateReader() {
		return state;
	}
	
	public StateWriter getStateWriter() {
		return state;
	}

	public void restart() {
		unregisterTaskConsumers();
		
		state.clear();
		taskBroker.clear();
		stateServer.reload();
		registerTaskConsumers();
	}

	public void start() {
		taskBroker.clear();
		
		state.clear();
		persistentTaskBroker.clear();
		stateServer.reload();
		registerTaskConsumers();
	}

	public void unregisterTaskConsumers() {
		taskConsumerRegistrar.unregisterTaskConsumer(orchestratorId);
		taskConsumerRegistrar.unregisterTaskConsumer(deploymentPlannerId);
		taskConsumerRegistrar.unregisterTaskConsumer(capacityPlannerId);
		taskConsumerRegistrar.unregisterTaskConsumer(machineProvisionerId);
	}
	
	private void registerTaskConsumers() {
		taskConsumerRegistrar.registerTaskConsumer(newServiceGridOrchestrator(timeProvider), orchestratorId);
		taskConsumerRegistrar.registerTaskConsumer(newServiceGridDeploymentPlanner(timeProvider), deploymentPlannerId);
		taskConsumerRegistrar.registerTaskConsumer(newServiceGridCapacityPlanner(timeProvider), capacityPlannerId);
		taskConsumerRegistrar.registerTaskConsumer(newMachineProvisionerContainer(taskConsumerRegistrar), machineProvisionerId);
	}
	
	private ServiceGridOrchestrator newServiceGridOrchestrator(CurrentTimeProvider timeProvider) {
		
		final ServiceGridOrchestratorParameter serviceOrchestratorParameter = new ServiceGridOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorId(orchestratorId);
		serviceOrchestratorParameter.setMachineProvisionerId(machineProvisionerId);
		serviceOrchestratorParameter.setTaskReader(taskBroker);
		serviceOrchestratorParameter.setStateReader(state);
		serviceOrchestratorParameter.setTimeProvider(timeProvider);
	
		return new ServiceGridOrchestrator(serviceOrchestratorParameter);
	}

	private ServiceGridDeploymentPlanner newServiceGridDeploymentPlanner(CurrentTimeProvider timeProvider) {
		
		final ServiceGridDeploymentPlannerParameter servicePlannerParameter = new ServiceGridDeploymentPlannerParameter();
		servicePlannerParameter.setOrchestratorId(orchestratorId);
		return new ServiceGridDeploymentPlanner(servicePlannerParameter);
	}
	
	private ServiceGridCapacityPlanner newServiceGridCapacityPlanner(CurrentTimeProvider timeProvider) {
		
		final ServiceGridCapacityPlannerParameter servicePlannerParameter = new ServiceGridCapacityPlannerParameter();
		servicePlannerParameter.setDeploymentPlannerId(deploymentPlannerId);
		servicePlannerParameter.setTaskReader(taskBroker);
		servicePlannerParameter.setStateReader(state);
		return new ServiceGridCapacityPlanner(servicePlannerParameter);
		
	}

	private MockMachineProvisioner newMachineProvisionerContainer(TaskConsumerRegistrar taskConsumerRegistrar) {
		return new MockMachineProvisioner(taskConsumerRegistrar); 
	}

	public TaskReader getPersistentTaskReader() {
		return persistentTaskBroker;
	}

	public TaskWriter getPersistentTaskWriter() {
		return persistentTaskBroker;
	}

	public URI getCapacityPlannerId() {
		return capacityPlannerId;
	}

	public void close() {
		stateServer.stop();
	}
}
