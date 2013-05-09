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


import com.google.common.base.Objects;

/**
 * Holds status information of an executed task.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class TaskStatusMessage extends AbstractTaskMessage {

    public static final String SENT = "task_sent";
    public static final String RECEIVED = "task_received";
    public static final String STARTED = "task_started";
    public static final String COMPLETED = "task_completed";
    public static final String FAILED = "task_failed";

    private String status;

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    @Override
    public String toString() {
        return Objects.toStringHelper(this)
                .add("taskId", getTaskId())
                .add("target", getTarget())
                .add("sender", getSender())
                .add("status", status)
                .toString();
    }
}
