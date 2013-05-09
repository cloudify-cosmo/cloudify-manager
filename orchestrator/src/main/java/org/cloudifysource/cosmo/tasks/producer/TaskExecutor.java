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
import com.google.common.base.Preconditions;
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
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.cloudifysource.cosmo.tasks.messages.TaskStatusMessage;

import java.net.URI;
import java.util.UUID;

/**
 * Client for sending tasks using the broker based messaging infrastructure.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class TaskExecutor {

    private final Logger logger;
    private final MessageProducer producer;
    private final MessageConsumer consumer;

    public TaskExecutor(MessageProducer producer, MessageConsumer consumer) {
        this.producer = producer;
        this.consumer = consumer;
        this.logger = LoggerFactory.getLogger(getClass());
    }

    public void send(URI topic, ExecuteTaskMessage task) {
        send(topic, task, null);
    }

    public void send(URI topic, final ExecuteTaskMessage task, final TaskExecutorListener listener) {
        task.setTaskId(generateTaskId());
        if (listener != null) {
            consumer.addListener(topic, new MessageConsumerListener<Object>() {
                @Override
                public void onMessage(URI uri, Object message) {
                    if (message instanceof TaskStatusMessage) {
                        logger.debug("Received task status: {}", message);
                        final TaskStatusMessage taskStatusMessage = (TaskStatusMessage) message;
                        if (areSameTasks(task, taskStatusMessage)) {
                            listener.onTaskStatusReceived(taskStatusMessage);
                        }
                    }
                }
                @Override
                public void onFailure(Throwable t) {
                    listener.onFailure(t);
                }
            });
        }

        final ListenableFuture future = producer.send(topic, task);

        if (listener != null) {
            Futures.addCallback(future, new FutureCallback<Response>() {
                @Override
                public void onSuccess(Response result) {
                    if (result.getStatusCode() != 200) {
                        onFailure(new RuntimeException("HTTP status code is: " + result.getStatusCode()));
                    }
                    final ExecuteTaskMessage taskResult = new ExecuteTaskMessage();

                    final TaskStatusMessage message = new TaskStatusMessage();
                    message.setTaskId(task.getTaskId());
                    message.setSender(task.getSender());
                    message.setTarget(task.getTarget());
                    message.setStatus(TaskStatusMessage.SENT);
                    listener.onTaskStatusReceived(message);
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

    private boolean areSameTasks(ExecuteTaskMessage newTaskMessage, TaskStatusMessage taskStatusMessage) {
        Preconditions.checkNotNull(taskStatusMessage);
        return Objects.equal(newTaskMessage.getTaskId(), taskStatusMessage.getTaskId()) &&
                Objects.equal(newTaskMessage.getTarget(), taskStatusMessage.getTarget()) &&
                Objects.equal(newTaskMessage.getSender(), taskStatusMessage.getSender());
    }

    private String generateTaskId() {
        return UUID.randomUUID().toString();
    }

    /**
     * Creates a new {@link ExecuteTaskMessage} instance and assigns it with a unique task id.
     * @param target The target of the task (recipient).
     * @param sender The sender of the task.
     * @return {@link ExecuteTaskMessage} instance.
     */
    public ExecuteTaskMessage createTask(String target, String sender) {
        Preconditions.checkNotNull(target, "task target cannot be null");
        Preconditions.checkNotNull(sender, "task sender cannot be null");
        final ExecuteTaskMessage message = new ExecuteTaskMessage();
        message.setTaskId(generateTaskId());
        message.setTarget(target);
        message.setSender(sender);
        return message;
    }
}
