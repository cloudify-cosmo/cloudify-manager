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
 * This class is in charge of cloud resources provisioning using a specified {@link CloudDriver} instance.
 * <p>Provisioning requests are passed through a messaging broker which the provisioner is listening to.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class CloudResourceProvisioner {

    private final Logger logger;
    private final CloudDriver driver;
    private final MessageConsumer consumer;
    private final MessageConsumerListener<CloudResourceMessage> listener;

    public CloudResourceProvisioner(final CloudDriver driver, URI inputUri, MessageConsumer consumer) {
        this.logger = LoggerFactory.getLogger(getClass());
        this.driver = driver;
        this.consumer = consumer;
        this.listener = new MessageConsumerListener<CloudResourceMessage>() {
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
        };
        consumer.addListener(inputUri, listener);
    }

    public void close() {
        consumer.removeListener(listener);
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
