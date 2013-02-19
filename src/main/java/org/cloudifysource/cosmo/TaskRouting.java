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
package org.cloudifysource.cosmo;

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
