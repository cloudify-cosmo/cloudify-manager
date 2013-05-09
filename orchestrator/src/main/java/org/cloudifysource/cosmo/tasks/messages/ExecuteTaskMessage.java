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

import com.google.common.base.Optional;
import com.google.common.collect.Maps;

import java.util.Map;
import java.util.Objects;

/**
 * An execute task object to be sent using a {@link org.cloudifysource.cosmo.tasks.producer.TaskExecutor}.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class ExecuteTaskMessage extends AbstractTaskMessage {

    private Map<String, Object> payload;


    public Map<String, Object> getPayload() {
        return payload;
    }

    public void setPayload(Map<String, Object> payload) {
        this.payload = payload;
    }

    public void put(String key, String value) {
        if (payload == null)
            payload = Maps.newHashMap();
        payload.put(key, value);
    }

    public Optional<Object> get(String key) {
        final Object value = payload != null && payload.containsKey(key) ? payload.get(key) : null;
        return Optional.fromNullable(value);
    }

    @Override
    public String toString() {
        return com.google.common.base.Objects.toStringHelper(this)
                .add("taskId", getTaskId())
                .add("target", getTarget())
                .add("sender", getSender())
                .add("payload", payload)
                .toString();
    }
}
