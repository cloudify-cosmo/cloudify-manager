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
package org.openspaces.servicegrid.service;

import java.net.URI;

public class ServiceGridDeploymentPlannerParameter {
	
	private URI orchestratorId;
	private URI agentsId;
	private URI deploymentPlannerId;
	
	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public void setOrchestratorId(URI orchestratorId) {
		this.orchestratorId = orchestratorId;
	}

	public URI getAgentsId() {
		return agentsId;
	}

	public void setAgentsId(URI agentsId) {
		this.agentsId = agentsId;
	}

	public void setDeploymentPlannerId(URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}

	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}
}
