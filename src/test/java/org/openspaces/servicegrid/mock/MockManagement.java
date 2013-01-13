package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.net.URISyntaxException;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.service.ServiceGridDeploymentPlanner;
import org.openspaces.servicegrid.service.ServiceGridOrchestrator;
import org.openspaces.servicegrid.service.ServiceGridOrchestratorParameter;
import org.openspaces.servicegrid.service.ServiceGridPlannerParameter;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamWriter;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.google.common.base.Throwables;

public class MockManagement {

	private final URI orchestratorId;
	private final URI deploymentPlannerId;
	private final URI machineProvisionerId;
	private final MockStreams<TaskConsumerState> state;
	private final MockStreams<Task> taskBroker;
	private final CurrentTimeProvider timeProvider;
	private final TaskConsumerRegistrar taskConsumerRegistrar;
	
	
	public MockManagement(TaskConsumerRegistrar taskConsumerRegistrar, CurrentTimeProvider timeProvider)  {
		this.taskConsumerRegistrar = taskConsumerRegistrar;
		this.timeProvider = timeProvider;
		try {
			orchestratorId = new URI("http://localhost/services/orchestrator/");
			deploymentPlannerId = new URI("http://localhost/services/deploymentPlanner/");
			machineProvisionerId = new URI("http://localhost/services/provisioner/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
		state = new MockStreams<TaskConsumerState>();
		taskBroker = new MockStreams<Task>();
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public StreamReader<Task> getTaskReader() {
		return taskBroker;
	}

	public StreamWriter<Task> getTaskWriter() {
		return taskBroker;
	}
	
	public StreamReader<TaskConsumerState> getStateReader() {
		return state;
	}
	
	public StreamWriter<TaskConsumerState> getStateWriter() {
		return state;
	}

	public void restart() {
		unregisterTaskConsumers();
		state.clear();
		taskBroker.clear();
		registerTaskConsumers();
	}

	private void unregisterTaskConsumers() {
		taskConsumerRegistrar.unregisterTaskConsumer(orchestratorId);
		taskConsumerRegistrar.unregisterTaskConsumer(deploymentPlannerId);
		taskConsumerRegistrar.unregisterTaskConsumer(machineProvisionerId);
	}
	
	public void registerTaskConsumers() {
		taskConsumerRegistrar.registerTaskConsumer(newServiceGridOrchestrator(timeProvider), orchestratorId);
		taskConsumerRegistrar.registerTaskConsumer(newServiceGridDeploymentPlanner(timeProvider), deploymentPlannerId);
		taskConsumerRegistrar.registerTaskConsumer(newMachineProvisionerContainer(taskConsumerRegistrar), machineProvisionerId);
	}
	
	private ServiceGridOrchestrator newServiceGridOrchestrator(CurrentTimeProvider timeProvider) {
		
		final ServiceGridOrchestratorParameter serviceOrchestratorParameter = new ServiceGridOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorId(orchestratorId);
		serviceOrchestratorParameter.setMachineProvisionerId(machineProvisionerId);
		serviceOrchestratorParameter.setDeploymentPlannerId(deploymentPlannerId);
		serviceOrchestratorParameter.setTaskConsumer(taskBroker);
		serviceOrchestratorParameter.setStateReader(state);
		serviceOrchestratorParameter.setTimeProvider(timeProvider);
	
		return new ServiceGridOrchestrator(serviceOrchestratorParameter);
	}

	private ServiceGridDeploymentPlanner newServiceGridDeploymentPlanner(CurrentTimeProvider timeProvider) {
		
		final ServiceGridPlannerParameter servicePlannerParameter = new ServiceGridPlannerParameter();
		servicePlannerParameter.setOrchestratorId(orchestratorId);
		servicePlannerParameter.setTimeProvider(timeProvider);
		
		return new ServiceGridDeploymentPlanner(servicePlannerParameter);
		
	}

	private MockMachineProvisioner newMachineProvisionerContainer(TaskConsumerRegistrar taskConsumerRegistrar) {
		return new MockMachineProvisioner(taskConsumerRegistrar); 
	}
}
