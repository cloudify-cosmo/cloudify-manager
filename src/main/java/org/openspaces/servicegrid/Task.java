package org.openspaces.servicegrid;

import java.net.URI;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.databind.annotation.JsonTypeIdResolver;

@JsonTypeIdResolver(TaskTypeIdResolver.class)
@JsonTypeInfo(use=JsonTypeInfo.Id.CUSTOM, include=JsonTypeInfo.As.PROPERTY, property="task", visible=false)
public class Task {
	
	private final Class<? extends TaskConsumerState> stateClass;

	private URI stateId;

	private URI consumerId;

	private URI producerId;

	private Long producerTimestamp;

	public Task(Class<? extends TaskConsumerState> stateClass) {
		this.stateClass = stateClass;
	}

	@JsonIgnore
	public Class<? extends TaskConsumerState> getStateClass() {
		return stateClass;
	}
	
	public URI getStateId() {
		return stateId;
	}

	public void setStateId(URI stateId) {
		this.stateId = stateId;
	}

	public URI getProducerId() {
		return producerId;
	}

	public void setConsumerId(URI consumerId) {
		this.consumerId = consumerId;
	}
	
	public URI getConsumerId() {
		return consumerId;
	}

	public void setSource(URI source) {
		this.setProducerId(source);
	}

	public Long getProducerTimestamp() {
		return producerTimestamp;
	}

	public void setProducerTimestamp(Long sourceTimestamp) {
		this.producerTimestamp = sourceTimestamp;
	}

	public void setProducerId(URI producerId) {
		this.producerId = producerId;
	}
}
