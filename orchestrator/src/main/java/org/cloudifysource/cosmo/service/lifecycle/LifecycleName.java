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

import com.google.common.base.Preconditions;
import com.google.common.base.Objects;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The name of a {@link LifecycleStateMachine} and the prefix of {@link LifecycleState}s.
 * {@link LifecycleName} example: name="tomcat"
 * {@link LifecycleState} example: name="tomcat_started"
 * {@link LifecycleStateMachine} example: name="tomcat", text="tomcat_stopped<->tomcat_started"
 * @author itaif
 * @since 0.1
 */
public class LifecycleName {

    static final Pattern LIFECYCLE_STATE_NAME_PATTERN = Pattern.compile("(\\w+)_(?=(\\w+))");

    String name;

    /**
     * deserialization cotr.
     */
    public LifecycleName() {

    }

    public LifecycleName(String name) {
        setName(name);
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        Preconditions.checkArgument(!name.contains("_"), "%s cannot contain underscore", name);
        this.name = name;
    }

    public void validateLifecycleStateName(LifecycleState state) {
        Preconditions.checkNotNull(state);
        final Matcher matcher = LIFECYCLE_STATE_NAME_PATTERN.matcher(state.getName());
        boolean found = false;
        while (matcher.find()) {
            Preconditions.checkArgument(
                    !found,
                    "%s should contain the underscore _ character only once",
                    state.getName());
            Preconditions.checkArgument(
                    matcher.group(1).equals(name),
                    "%s should start with %s_",
                    state.getName(), name);
            found = true;
        }
        Preconditions.checkArgument(found, "%s should start with %s_", state.getName(), name);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof LifecycleName)) return false;

        LifecycleName that = (LifecycleName) o;

        return Objects.equal(name, that.name);

    }

    public static LifecycleName fromLifecycleState(LifecycleState state) {
        final Matcher matcher = LIFECYCLE_STATE_NAME_PATTERN.matcher(state.getName());
        LifecycleName lifecycleName = null;
        while (matcher.find()) {
            Preconditions.checkArgument(
                    lifecycleName == null,
                    "The underscore _ character should appear only once in %s",
                    state.getName());
            lifecycleName = new LifecycleName(matcher.group(1));
        }
        Preconditions.checkArgument(
                lifecycleName != null,
                "The underscore _ character should appear in %s", state.getName());
        return lifecycleName;
    }

    @Override
    public int hashCode() {
        return name.hashCode();
    }
}
