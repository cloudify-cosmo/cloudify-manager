/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.cloudifysource.cosmo.mock;

import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.kvstore.KVStoreServer;
import org.cloudifysource.cosmo.StateClient;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.TaskWriter;
import org.cloudifysource.cosmo.service.*;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.state.StateWriter;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;
import java.net.URISyntaxException;

public class MockManagement {

	private static final int STATE_SERVER_PORT = 8080;
	private static final String STATE_SERVER_URI = "http://localhost:"+STATE_SERVER_PORT+"/";
	private static final boolean useMock = true;
	private final URI orchestratorId;
	private final URI deploymentPlannerId;
	private final URI capacityPlannerId;
	private final URI machineProvisionerId;
	private final StateReader stateReader;
	private final StateWriter stateWriter;
	private final MockTaskBroker taskBroker;
	private final CurrentTimeProvider timeProvider;
	private final TaskConsumerRegistrar taskConsumerRegistrar;
	private final MockTaskBroker persistentTaskBroker;
	private KVStoreServer stateServer;
	
	public MockManagement(TaskConsumerRegistrar taskConsumerRegistrar, CurrentTimeProvider timeProvider)  {
		this.taskConsumerRegistrar = taskConsumerRegistrar;
		this.timeProvider = timeProvider;
		try {
			orchestratorId = new URI(STATE_SERVER_URI+"services/orchestrator/");
			deploymentPlannerId = new URI(STATE_SERVER_URI+"services/deployment_planner/");
			capacityPlannerId = new URI(STATE_SERVER_URI+"services/capacity_planner/");
			machineProvisionerId = new URI(STATE_SERVER_URI+"services/provisioner/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
		if (useMock) {
			stateReader = new MockState();
			stateWriter = (StateWriter) stateReader;
			((MockState)stateReader).setLoggingEnabled(false);
		}
		else {
			stateReader = new StateClient(StreamUtils.newURI(STATE_SERVER_URI));
			stateWriter = (StateWriter) stateReader;
			stateServer = new KVStoreServer();
			stateServer.start(STATE_SERVER_PORT);
		}
		taskBroker = new MockTaskBroker();
		taskBroker.setLoggingEnabled(false);
		persistentTaskBroker = new MockTaskBroker();
		
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
		return stateReader;
	}
	
	public StateWriter getStateWriter() {
		return stateWriter;
	}

	public void restart() {
		unregisterTaskConsumers();
		clearState();
		taskBroker.clear();
		registerTaskConsumers();
	}

	private void clearState() {
		if (useMock) {
			((MockState)stateReader).clear();
		}
		else {
			stateServer.reload();			
		}
	}

	public void start() {

		clearState();
		taskBroker.clear();
		persistentTaskBroker.clear();
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
		serviceOrchestratorParameter.setStateReader(stateReader);
		serviceOrchestratorParameter.setTimeProvider(timeProvider);
	
		return new ServiceGridOrchestrator(serviceOrchestratorParameter);
	}

	private ServiceGridDeploymentPlanner newServiceGridDeploymentPlanner(CurrentTimeProvider timeProvider) {
		
		final ServiceGridDeploymentPlannerParameter deploymentPlannerParameter = new ServiceGridDeploymentPlannerParameter();
		deploymentPlannerParameter.setOrchestratorId(orchestratorId);
		deploymentPlannerParameter.setAgentsId(StreamUtils.newURI(STATE_SERVER_URI + "agents/"));
		deploymentPlannerParameter.setDeploymentPlannerId(deploymentPlannerId);
		return new ServiceGridDeploymentPlanner(deploymentPlannerParameter);
		
	}
	
	private ServiceGridCapacityPlanner newServiceGridCapacityPlanner(CurrentTimeProvider timeProvider) {
		
		final ServiceGridCapacityPlannerParameter capacityPlannerParameter = new ServiceGridCapacityPlannerParameter();
		capacityPlannerParameter.setDeploymentPlannerId(deploymentPlannerId);
		capacityPlannerParameter.setTaskReader(taskBroker);
		capacityPlannerParameter.setStateReader(stateReader);
		capacityPlannerParameter.setCapacityPlannerId(capacityPlannerId);
		return new ServiceGridCapacityPlanner(capacityPlannerParameter);
		
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
	
	public String getStateServerUri() {
		return STATE_SERVER_URI;
	}
}
