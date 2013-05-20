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
package org.cloudifysource.cosmo.provisioner;

import com.google.common.base.Objects;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.provisioner.messages.CloudResourceMessage;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.cloudifysource.cosmo.tasks.messages.TaskStatusMessage;

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
    private final MessageConsumerListener<Object> listener;

    public CloudResourceProvisioner(final CloudDriver driver,
                                    URI inputUri,
                                    final MessageProducer producer,
                                    MessageConsumer consumer) {
        this.logger = LoggerFactory.getLogger(getClass());
        this.driver = driver;
        this.consumer = consumer;
        this.listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                logger.debug("Consumed message from broker: " + message);

                if (message instanceof ExecuteTaskMessage) {
                    final ExecuteTaskMessage executeTaskMessage = (ExecuteTaskMessage) message;
                    final TaskStatusMessage taskStatusMessage = new TaskStatusMessage();
                    taskStatusMessage.setTaskId(executeTaskMessage.getTaskId());
                    taskStatusMessage.setStatus(TaskStatusMessage.STARTED);
                    if (executeTaskMessage.get("exec").isPresent() &&
                            Objects.equal(executeTaskMessage.get("exec").get(), "start_machine")) {
                        final Optional<Object> resourceId = executeTaskMessage.get("resource_id");
                        Preconditions.checkArgument(resourceId.isPresent());
                        startMachine((String) resourceId.get());
                        logger.debug("Sending task status message reply [uri={}, message={}]", uri, taskStatusMessage);
                        ListenableFuture future = producer.send(uri, taskStatusMessage);
                        Futures.addCallback(future, new FutureCallback() {
                            @Override
                            public void onSuccess(Object result) {
                                // do nothing
                            }

                            @Override
                            public void onFailure(Throwable t) {
                                logger.warn(ProvisionerLogDescription.MESSAGE_PRODUCER_ERROR, t);
                            }
                        });
                    }
                } else if (message instanceof CloudResourceMessage) {
                    final CloudResourceMessage cloudResourceMessage = (CloudResourceMessage) message;
                    if ("start_machine".equals(cloudResourceMessage.getAction())) {
                        startMachine(cloudResourceMessage.getResourceId());
                    }
                }
            }

            @Override
            public void onFailure(Throwable t) {
                logger.warn(ProvisionerLogDescription.MESSAGE_CONSUMER_ERROR, t);
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
        final MachineDetails machineDetails = driver.startMachine(config);
        logger.debug("Machine successfully started: {}", machineDetails);
    }

}
