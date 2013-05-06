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
 *******************************************************************************/
package org.cloudifysource.cosmo.resource;

import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.resource.messages.CloudResourceMessage;

import java.net.URI;

/**
 * This class is responsible for cloud resources provisioning using a specified {@link CloudDriver} instance.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class CloudResourceProvisioner {

    private final Logger logger;
    private final CloudDriver driver;
    private final MessageConsumer consumer;
    private final URI inputUri;

    public CloudResourceProvisioner(final CloudDriver driver, URI inputUri) {
        Preconditions.checkNotNull(driver);
        Preconditions.checkNotNull(inputUri);
        this.inputUri = inputUri;
        this.driver = driver;
        this.consumer = new MessageConsumer();
        this.logger = LoggerFactory.getLogger(getClass());
    }

    public void start() {
        consumer.addListener(inputUri, new MessageConsumerListener<CloudResourceMessage>() {
            @Override
            public void onMessage(URI uri, CloudResourceMessage message) {
                logger.debug("Consumed message from broker: " + message);
                if ("start_machine".equals(message.getAction())) {
                    startMachine(message.getResourceId());
                }
            }

            @Override
            public void onFailure(Throwable t) {
            }
        });
    }

    public void stop() {
        consumer.removeAllListeners();
    }

    private void startMachine(String id) {
        final MachineConfiguration config = new MachineConfiguration(id, "cosmo");
        logger.debug("Starting machine: {}", config);
        try {
            final MachineDetails machineDetails = driver.startMachine(config);
            logger.debug("Machine successfully started: {}", machineDetails);

        } catch (Exception e) {
            logger.debug("Error starting machine [config={}, exception={}]", config, e);
        }
    }

}
