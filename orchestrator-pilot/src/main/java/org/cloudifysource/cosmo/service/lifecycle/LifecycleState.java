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
package org.cloudifysource.cosmo.service.lifecycle;

import com.google.common.base.Objects;

/**
 * A string wrapper that represents a state inside a {@link LifecycleStateMachine}.
 * The name must start with the name of the state machine follows by an underscore.
 * @see LifecycleName#validateLifecycleStateName(LifecycleState)
 *
 * @author itaif
 * @since 0.1
 */
public class LifecycleState {

    String name;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    //deserialization cotr
    public LifecycleState() {

    }

    public LifecycleState(String name) {
        setName(name);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof LifecycleState)) return false;

        LifecycleState that = (LifecycleState) o;

        return Objects.equal(name, that.name);

    }

    @Override
    public int hashCode() {
        return name.hashCode();
    }

    @Override
    public String toString() {
        return "LifecycleState{" +
                "name='" + name + '\'' +
                '}';
    }
}



