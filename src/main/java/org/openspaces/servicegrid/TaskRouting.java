package org.openspaces.servicegrid;

import java.net.URI;

public class TaskRouting {
	private URI stateId;
	private URI consumerId;
	private URI producerId;
	private Long producerTimestamp;

	public URI getStateId() {
		return stateId;
	}

	public void setStateId(URI stateId) {
		this.stateId = stateId;
	}

	public URI getConsumerId() {
		return consumerId;
	}

	public void setConsumerId(URI consumerId) {
		this.consumerId = consumerId;
	}

	public URI getProducerId() {
		return producerId;
	}

	public void setProducerId(URI producerId) {
		this.producerId = producerId;
	}

	public Long getProducerTimestamp() {
		return producerTimestamp;
	}

	public void setProducerTimestamp(Long producerTimestamp) {
		this.producerTimestamp = producerTimestamp;
	}
}