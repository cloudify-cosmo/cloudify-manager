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
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.resource.messages.CloudResourceMessage;

import java.net.URI;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class CloudResourceProvisioner {

    private static final Logger LOGGER = LoggerFactory.getLogger(CloudResourceProvisioner.class);

    private final CloudDriver driver;
    private final MessageConsumer consumer;
    private final URI inputUri;

    public CloudResourceProvisioner(final CloudDriver driver, URI inputUri) {
        Preconditions.checkNotNull(driver);
        Preconditions.checkNotNull(inputUri);
        this.inputUri = inputUri;
        this.driver = driver;
        this.consumer = new MessageConsumer();
    }

    public void start() {
        consumer.addListener(inputUri, new MessageConsumerListener<CloudResourceMessage>() {
            @Override
            public void onMessage(URI uri, CloudResourceMessage message) {
                LOGGER.debug("Consumed message from broker: " + message);
                if ("start_machine".equals(message.getAction())) {
                    startMachine(message.getId());
                }
            }

            @Override
            public void onFailure(Throwable t) {
            }

            @Override
            public Class<? extends CloudResourceMessage> getMessageClass() {
                return CloudResourceMessage.class;
            }

        });
    }

    public void stop() {
        consumer.removeAllListeners();
    }

    private void startMachine(String id) {
        driver.startMachine(new MachineConfiguration(id, "cosmo"));
    }

}
