package org.cloudifysource.cosmo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.agent.state.AgentState;

import java.util.ArrayList;
import java.util.List;

public class LifecycleStateMachine {

    private List<String> stateMachine;

    public LifecycleStateMachine() {

    }

    public LifecycleStateMachine(ArrayList<String> stateMachine) {
        this();
        this.stateMachine = stateMachine;
    }

    public List<String> getStateMachine() {
        return stateMachine;
    }

    public void setStateMachine(List<String> stateMachine) {
        this.stateMachine = stateMachine;
    }

    /**
     * @return the initial state of the lifecycle state machine.
     */
    @JsonIgnore
    public String getInitialLifecycle() {
        return stateMachine.get(0);
    }

    @JsonIgnore
    public String getFinalInstanceLifecycle() {
        return Iterables.getLast(stateMachine);
    }

    /**
     * @param lifecycle - the current lifecycle
     * @return - the next lifecycle state
     *           or the specified lifecycle if this is the last lifecycle,
     *           or null if the specified lifecycle is not part of the state machine.
     */
    @JsonIgnore
    public String getNextInstanceLifecycle(String lifecycle) {
        if (lifecycle.equals(AgentState.Progress.AGENT_STARTED)) {
            return getInitialLifecycle();
        }
        int index = toInstanceLifecycleIndex(lifecycle);
        if (index < 0) {
            return null;
        }

        final int lastIndex = stateMachine.size() - 1;
        if (index  < lastIndex) {
            index++;
        }
        return stateMachine.get(index);
    }

    /**
     * @param lifecycle - the current instance lifecycle
     * @return - the prev lifecycle
     *           or lifecycle if there is no previous lifecycle,
     *           or null if the specified lifecycle is not part of the state machine
     */
    @JsonIgnore
    public String getPrevInstanceLifecycle(String lifecycle) {
        if (lifecycle.equals(AgentState.Progress.MACHINE_UNREACHABLE)) {
            return lifecycle;
        }

        int index = toInstanceLifecycleIndex(lifecycle);
        if (index < 0) {
            return null;
        }

        if (index == 0) {
            return lifecycle;
        }

        return stateMachine.get(index - 1);
    }

    private int toInstanceLifecycleIndex(String lifecycle) {
        Preconditions.checkNotNull(lifecycle);
        return this.stateMachine.indexOf(lifecycle);
    }
}
