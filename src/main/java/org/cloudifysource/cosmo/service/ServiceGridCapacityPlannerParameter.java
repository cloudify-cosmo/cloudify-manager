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
package org.cloudifysource.cosmo.service;

import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.state.StateReader;

import java.net.URI;

public class ServiceGridCapacityPlannerParameter {

	private URI deploymentPlannerId;
	private TaskReader taskReader;
	private StateReader stateReader;
	private URI capacityPlannerId;

	public void setDeploymentPlannerId(final URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public StateReader getStateReader() {
		return stateReader;
	}

	public TaskReader getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(TaskReader taskReader) {
		this.taskReader = taskReader;
	}

	public void setStateReader(StateReader stateReader) {
		this.stateReader = stateReader;
	}

	public URI getCapacityPlannerId() {
		return capacityPlannerId;
	}

	public void setCapacityPlannerId(URI capacityPlannerId) {
		this.capacityPlannerId = capacityPlannerId;
	}
}
