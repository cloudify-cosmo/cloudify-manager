package org.openspaces.servicegrid;

import java.net.URI;

import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.databind.annotation.JsonTypeIdResolver;

@JsonTypeIdResolver(TaskTypeIdResolver.class)
@JsonTypeInfo(use=JsonTypeInfo.Id.CUSTOM, include=JsonTypeInfo.As.PROPERTY, property="task", visible=false)
public class Task {

	private URI consumerId;

	private URI producerId;

	private Long producerTimestamp;

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
		this.producerId = source;
	}

	public Long getProducerTimestamp() {
		return producerTimestamp;
	}

	public void setProducerTimestamp(Long sourceTimestamp) {
		this.producerTimestamp = sourceTimestamp;
	}
}
