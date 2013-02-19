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
package org.openspaces.servicegrid;

import java.net.URI;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.databind.annotation.JsonTypeIdResolver;

@JsonTypeIdResolver(TaskTypeIdResolver.class)
@JsonTypeInfo(use=JsonTypeInfo.Id.CUSTOM, include=JsonTypeInfo.As.PROPERTY, property="task", visible=false)
public abstract class Task {
	
	private TaskRouting routing;
	private final Class<? extends TaskConsumerState> stateClass;

	public Task(Class<? extends TaskConsumerState> stateClass) {
		routing = new TaskRouting();
		this.stateClass = stateClass;
	}
	
	@JsonIgnore
	public Class<? extends TaskConsumerState> getStateClass() {
		return stateClass;
	}
	
	@JsonIgnore
	public URI getStateId() {
		return routing.getStateId();
	}

	public void setStateId(URI stateId) {
		this.routing.setStateId(stateId);
	}

	@JsonIgnore
	public URI getProducerId() {
		return routing.getProducerId();
	}

	public void setConsumerId(URI consumerId) {
		this.routing.setConsumerId(consumerId);
	}
	
	@JsonIgnore
	public URI getConsumerId() {
		return routing.getConsumerId();
	}

	@JsonIgnore
	public Long getProducerTimestamp() {
		return routing.getProducerTimestamp();
	}

	public void setProducerTimestamp(Long sourceTimestamp) {
		this.routing.setProducerTimestamp(sourceTimestamp);
	}

	public void setProducerId(URI producerId) {
		this.routing.setProducerId(producerId);
	}

	public TaskRouting getRouting() {
		return routing;
	}

	public void setRouting(TaskRouting routing) {
		this.routing = routing;
	}
}
