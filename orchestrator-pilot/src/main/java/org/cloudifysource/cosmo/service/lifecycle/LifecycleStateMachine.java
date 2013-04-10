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

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonUnwrapped;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * A state machine implementation.
 * @author itaif
 * @since 0.1
 */
public class LifecycleStateMachine {

    //state changes from one state into zero or more other states.
    private Map<LifecycleState, Set<LifecycleState>> indexedStateMachine;
    private LifecycleState beginState;
    private LifecycleState endState;
    private LifecycleState currentState;
    private LifecycleStateMachineText text;
    private LifecycleName name;
    private Map<String, String> properties = Maps.newLinkedHashMap();

    /**
     * Deserialization cotr.
     */
    public LifecycleStateMachine() {
    }

    public LifecycleState getCurrentState() {
        if (currentState == null) {
            return getBeginState();
        }
        return currentState;
    }

    public void setCurrentState(LifecycleState currentState) {
        this.currentState = currentState;
    }

    public LifecycleName getLifecycleName() {
        return name;
    }

    public void setLifecycleName(LifecycleName name) {
        this.name = name;
    }

    public void setEndState(LifecycleState endState) {
        this.endState = endState;
    }

    public void setBeginState(LifecycleState beginState) {
        this.beginState = beginState;
    }

    void addStateTransition(LifecycleState fromLifecycle, LifecycleState toLifecycle) {
        addState(fromLifecycle);
        addState(toLifecycle);
        indexedStateMachine.get(fromLifecycle).add(toLifecycle);
    }

    void addState(LifecycleState state) {
        this.name.validateLifecycleStateName(state);
        if (!indexedStateMachine.containsKey(state)) {
            indexedStateMachine.put(state, Sets.<LifecycleState>newLinkedHashSet());
        }
    }

    /**
     * @param desiredLifecycle - the lifecycle state to eventually achieve.
     * @return - the next lifecycle state
     *           or currentLifecycle if currentLifecycle equals desiredLifecycle
     *           or null if the desired lifecycle cannot be reached.
     */
    @JsonIgnore
    public LifecycleState getNextLifecycleState(LifecycleState desiredLifecycle) {

        lazyInit();
        this.name.validateLifecycleStateName(desiredLifecycle);

        if (indexedStateMachine.containsKey(desiredLifecycle)) {
            return findNext(desiredLifecycle).orNull();
        }
        return null;
    }

    private void lazyInit() {
        this.name.validateLifecycleStateName(endState);
        this.name.validateLifecycleStateName(beginState);
        this.name.validateLifecycleStateName(getCurrentState());
        if (indexedStateMachine == null) {
            indexedStateMachine = Maps.newLinkedHashMap();
            text.parse(this);
        }
    }

    public LifecycleState getBeginState() {
        return beginState;
    }

    public LifecycleState getEndState() {
        return endState;
    }

    /**
     * Finds the next state that would bring us closer from current state
     * to the desired state.
     * @param desiredState - the last state (stop condition)
     * @return the next step to walk on the state machine.
     */
    Optional<LifecycleState> findNext(LifecycleState desiredState) {

        if (getCurrentState().equals(desiredState)) {
            //edge case - already in desired state.
            return Optional.fromNullable(getCurrentState());
        }

        //used to prevent endless loops in traversing the state machine.
        final Set<LifecycleState> visited = Sets.newLinkedHashSet();
        //stack to remember which parts we already scanned.
        final LinkedList<List<LifecycleState>> childrenStack = Lists.newLinkedList();
        //inject children of initial state
        visited.add(getCurrentState());
        Preconditions.checkState(indexedStateMachine.containsKey(getCurrentState()),
                "Cannot find current state %s in state machine", getCurrentState());
        childrenStack.add(Lists.newArrayList(indexedStateMachine.get(getCurrentState())));

        while (true) {
            Preconditions.checkState(childrenStack.size() <= this.indexedStateMachine.size());
            if (childrenStack.isEmpty()) {
                // no more states to scan, no path exists.
                return Optional.absent();
            }
            final List<LifecycleState> childs = Iterables.getLast(childrenStack);
            if (childs.isEmpty()) {
                //scanned all children did not find desired state,
                //backtracking ...
                childrenStack.removeLast();
                continue;
            }
            LifecycleState state = childs.get(0);
            if (visited.contains(state)) {
                //loop - already scanned this child, ignore
                childs.remove(0);
                continue;
            }
            visited.add(state);

            if (state.equals(desiredState)) {
                // path to desired state exists, return first child
                return Optional.fromNullable(childrenStack.get(0).get(0));
            }

            // iterate over all children
            final Set<LifecycleState> children = indexedStateMachine.get(state);
            childrenStack.add(Lists.newArrayList(children));
        }
    }

    @JsonUnwrapped
    public LifecycleStateMachineText getText() {
        return text;
    }

    /**
     * @param text - text based representation of state machine.
     * @see LifecycleStateMachineText
     */
    public void setText(LifecycleStateMachineText text) {
        this.text = text;
        indexedStateMachine = null;
    }

    @JsonIgnore
    public boolean isLifecycleEndState() {
        return isLifecycleState(getEndState());
    }

    @JsonIgnore
    public boolean isLifecycleBeginState() {
        return isLifecycleState(getBeginState());
    }

    public boolean isLifecycleState(LifecycleState expectedLifecycleState) {
        return getCurrentState().equals(expectedLifecycleState);
    }

    public Map<String, String> getProperties() {
        return properties;
    }

    public void setProperties(Map<String, String> properties) {
        this.properties = properties;
    }
}
