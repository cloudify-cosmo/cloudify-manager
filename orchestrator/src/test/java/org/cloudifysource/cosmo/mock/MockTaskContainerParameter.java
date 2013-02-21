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
package org.cloudifysource.cosmo.mock;

import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.TaskWriter;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.state.StateWriter;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;

public class MockTaskContainerParameter {
    private URI executorId;
    private StateReader stateReader;
    private StateWriter stateWriter;
    private TaskReader taskReader;
    private TaskWriter taskWriter;
    private Object taskConsumer;
    private CurrentTimeProvider timeProvider;
    private TaskReader persistentTaskReader;
    private TaskWriter persistentTaskWriter;

    public MockTaskContainerParameter() {
    }

    public StateReader getStateReader() {
        return stateReader;
    }

    public void setStateReader(StateReader stateReader) {
        this.stateReader = stateReader;
    }

    public URI getExecutorId() {
        return executorId;
    }

    public void setExecutorId(URI executorId) {
        this.executorId = executorId;
    }

    public StateWriter getStateWriter() {
        return stateWriter;
    }

    public void setStateWriter(StateWriter stateWriter) {
        this.stateWriter = stateWriter;
    }

    public TaskWriter getTaskWriter() {
        return taskWriter;
    }

    public void setTaskWriter(TaskWriter taskWriter) {
        this.taskWriter = taskWriter;
    }

    public Object getTaskConsumer() {
        return taskConsumer;
    }

    public void setTaskConsumer(Object taskConsumer) {
        this.taskConsumer = taskConsumer;
    }

    public TaskReader getTaskReader() {
        return taskReader;
    }

    public void setTaskReader(TaskReader taskReader) {
        this.taskReader = taskReader;
    }

    public CurrentTimeProvider getTimeProvider() {
        return timeProvider;
    }

    public void setTimeProvider(CurrentTimeProvider timeProvider) {
        this.timeProvider = timeProvider;
    }

    public TaskReader getPersistentTaskReader() {
        return persistentTaskReader;
    }

    public void setPersistentTaskReader(TaskReader persistentTaskReader) {
        this.persistentTaskReader = persistentTaskReader;
    }

    public TaskWriter getPersistentTaskWriter() {
        return persistentTaskWriter;
    }

    public void setPersistentTaskWriter(TaskWriter persistentTaskWriter) {
        this.persistentTaskWriter = persistentTaskWriter;
    }
}
