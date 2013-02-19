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
package org.openspaces.servicegrid.service.state;

import java.net.URI;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;

public class ServiceInstanceState extends TaskConsumerState {
	
	private String progress;
	private URI agentId;
	private URI serviceId;
	private boolean unreachable;
	
	public void setProgress(String progress) {
		this.progress = progress;
	}

	public URI getAgentId() {
		return agentId;
	}

	public void setAgentId(URI agentId) {
		this.agentId = agentId;
	}

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

	/**
	 * Use isProgress(x or y or z) instead. 
	 * This is to encourage using the pattern of positive progress checks such as "isProgress(y)" 
	 * instead of negative progress checks such as (!getProgress().equals(x)) 
	 */
	@Deprecated
	public String getProgress() {
		return progress;
	}

	/**
	 * @return true if {@code #getProgress()} matches any of the specified options.
	 */
	public boolean isProgress(String ... expectedProgresses) {
		for (String expectedProgress : expectedProgresses) {
			if (progress != null && progress.equals(expectedProgress)) {
				return true;
			}
		}
		return false;
	}

	public void setUnreachable(boolean unreachable) {
		this.unreachable = unreachable;
	}
	
	public boolean isUnreachable() {
		return this.unreachable;
	}

	@JsonIgnore
	public boolean isProgressNull() {
		return progress == null;
	}
}
