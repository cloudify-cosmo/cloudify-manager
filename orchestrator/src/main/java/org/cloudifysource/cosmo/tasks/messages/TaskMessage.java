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
package org.cloudifysource.cosmo.tasks.messages;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.google.common.base.Objects;
import com.google.common.collect.Maps;

import java.util.Map;

/**
 * A task object to be sent using a {@link org.cloudifysource.cosmo.tasks.producer.TaskProducer}.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class TaskMessage {

    public static final String TASK_CREATED = "task_created";
    public static final String TASK_SENT = "task_sent";
    public static final String TASK_RECEIVED = "task_received";

    private String taskId;
    private Map<String, Object> payload;
    private String status;

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String id) {
        this.taskId = id;
    }

    @JsonAnyGetter
    public Map<String, Object> getPayload() {
        return payload;
    }

    public void setPayload(Map<String, Object> payload) {
        this.payload = payload;
    }

    @JsonAnySetter
    protected void handleUnknownProperty(String key, Object value) {
        if (payload == null)
            payload = Maps.newHashMap();
        payload.put(key, value);
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getStatus() {
        return status;
    }

    @Override
    public String toString() {
        return Objects.toStringHelper(getClass()).add("taskId", taskId).add("status", status).add("payload", payload)
                .toString();
    }
}
