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
package org.cloudifysource.cosmo.tasks.producer;

import com.google.common.base.Objects;
import com.google.common.base.Throwables;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.ning.http.client.Response;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.tasks.messages.TaskMessage;

import java.net.URI;
import java.util.UUID;

/**
 * Client for sending tasks using the broker infrastructure.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class TaskProducer {

    private final Logger logger;
    private final MessageProducer producer;
    private final MessageConsumer consumer;

    public TaskProducer(MessageProducer producer, MessageConsumer consumer) {
        this.producer = producer;
        this.consumer = consumer;
        this.logger = LoggerFactory.getLogger(getClass());
    }

    public void send(URI topic, TaskMessage task) {
        send(topic, task, null);
    }

    public void send(URI topic, final TaskMessage task, final TaskProducerListener listener) {
        task.setTaskId(generateTaskId());
        consumer.addListener(topic, new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                if (message instanceof TaskMessage) {
                    final TaskMessage result = (TaskMessage) message;
                    if (Objects.equal(task.getTaskId(), result.getTaskId()) && !Objects.equal(TaskMessage.TASK_CREATED,
                            result.getStatus())) {
                        logger.debug("Received task notification: {} for sent task: {}", result, task);
                        listener.onTaskUpdateReceived(result);
                    }
                }
            }
            @Override
            public void onFailure(Throwable t) {
                listener.onFailure(t);
            }
        });
        ListenableFuture future = producer.send(topic, task);
        if (listener != null) {
            Futures.addCallback(future, new FutureCallback<Response>() {
                @Override
                public void onSuccess(Response result) {
                    if (result.getStatusCode() != 200) {
                        onFailure(new RuntimeException("HTTP status code is: " + result.getStatusCode()));
                    }
                    final TaskMessage taskResult = new TaskMessage();
                    taskResult.setTaskId(task.getTaskId());
                    taskResult.setStatus(TaskMessage.TASK_SENT);
                    listener.onTaskUpdateReceived(taskResult);
                }

                @Override
                public void onFailure(Throwable t) {
                    listener.onFailure(t);
                }
            });
        } else {
            try {
                future.get();
            } catch (Exception e) {
                Throwables.propagate(e);
            }
        }
    }

    private String generateTaskId() {
        return UUID.randomUUID().toString();
    }
}
