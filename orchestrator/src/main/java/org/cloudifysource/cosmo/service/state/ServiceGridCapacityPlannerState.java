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
package org.cloudifysource.cosmo.service.state;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;
import java.util.List;

public class ServiceGridCapacityPlannerState extends TaskConsumerState {

	private List<ServiceScalingRule> scalingRules = Lists.newArrayList();

	public List<ServiceScalingRule> getScalingRules() {
		return scalingRules;
	}
	
	public void setScalingRules(List<ServiceScalingRule> scalingRules) {
		this.scalingRules = scalingRules;
	}

	@JsonIgnore
	public void addServiceScalingRule(ServiceScalingRule scalingRule) {
		removeServiceScalingRule(scalingRule.getServiceId());
		scalingRules.add(scalingRule);
	}
	
	@JsonIgnore
	public boolean removeServiceScalingRule(URI serviceId) {
		return Iterables.removeIf(scalingRules, findServiceIdPredicate(serviceId));
	}

	private Predicate<ServiceScalingRule> findServiceIdPredicate(final URI serviceId) {
		Preconditions.checkNotNull(serviceId);
		
		return new Predicate<ServiceScalingRule>() {

			@Override
			public boolean apply(ServiceScalingRule rule) {
				return serviceId.equals(rule.getServiceId());
			}
		};
	}


}
