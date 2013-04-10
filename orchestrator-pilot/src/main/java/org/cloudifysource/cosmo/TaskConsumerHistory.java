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
package org.cloudifysource.cosmo;

import com.google.common.collect.Lists;

import java.util.List;

/**
 * A list of tasks representing all tasks that were consumed by a {@link TaskConsumer}.
 * This list of tasks shaped the value {@link TaskConsumerState}.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class TaskConsumerHistory {

    private List<Task> tasksHistory = Lists.newArrayList();

    public List<Task> getTasksHistory() {
        return tasksHistory;
    }

    public void setTasksHistory(List<Task> tasksHistory) {
        this.tasksHistory = tasksHistory;
    }
}
