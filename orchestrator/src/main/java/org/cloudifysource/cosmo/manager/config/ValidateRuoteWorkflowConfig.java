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

package org.cloudifysource.cosmo.manager.config;

import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.inject.Inject;

/**
 * A configuration for creating a {@link RuoteWorkflow} instance for the validate plan workflow.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
@Configuration
public class ValidateRuoteWorkflowConfig {

    @Value("ruote/pdefs/validate_plan.radial")
    private String workflowRadialFile;

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Bean
    public RuoteWorkflow validateRuoteWorkflow() {
        return RuoteWorkflow.createFromResource(workflowRadialFile, ruoteRuntime);
    }

}
