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

public class ServiceScalingRule {

	private String propertyName;
	private Object highThreshold;
	private Object lowThreshold;
	private URI serviceId;
	
	public void setPropertyName(String valueName) {
		this.propertyName = valueName;
	}

	public void setHighThreshold(Object highThreshold) {
		this.highThreshold = highThreshold;
	}
	
	public String getPropertyName() {
		return propertyName;
	}
	
	public Object getHighThreshold() {
		return highThreshold;
	}

	public Object getLowThreshold() {
		return lowThreshold;
	}

	public void setLowThreshold(Object lowThreshold) {
		this.lowThreshold = lowThreshold;
	}

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
