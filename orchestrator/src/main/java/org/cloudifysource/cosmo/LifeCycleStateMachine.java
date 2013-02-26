package org.cloudifysource.cosmo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.agent.state.AgentState;

import java.util.ArrayList;
import java.util.List;

/**
 * A state machine implementation.
 * @author itaif
 * @since 0.1
 */
public class LifecycleStateMachine {

    //TODO: Reimplement using touples.
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
     * @param currentLifecycle - the current lifecycle
     * @param desiredLifecycle - the lifecycle state to eventually achieve.
     * @return - the next lifecycle state
     *           or currentLifecycle if currentLifecycle equals desiredLifecycle
     *           or null if the desired lifecycle cannot be reached.
     */
    @JsonIgnore
    public String getNextInstanceLifecycle(String currentLifecycle, String desiredLifecycle) {
        if (currentLifecycle.equals(AgentState.Progress.AGENT_STARTED)) {
            return getInitialLifecycle();
        }

        if (desiredLifecycle.equals(getFinalInstanceLifecycle())) {
            int index = toInstanceLifecycleIndex(currentLifecycle);
            if (index < 0) {
                return null;
            }

            final int lastIndex = stateMachine.size() - 1;
            if (index  < lastIndex) {
                index++;
            }
            return stateMachine.get(index);
        }
        else if (desiredLifecycle.equals(getInitialLifecycle())) {
            if (currentLifecycle.equals(AgentState.Progress.MACHINE_UNREACHABLE)) {
                return currentLifecycle;
            }

            int index = toInstanceLifecycleIndex(currentLifecycle);
            if (index < 0) {
                return null;
            }

            if (index == 0) {
                return currentLifecycle;
            }

            return stateMachine.get(index - 1);

        }
        else {
            Preconditions.checkState(false, "Unsupported yet.");
            //never reached
            return null;
        }
    }



    private int toInstanceLifecycleIndex(String lifecycle) {
        Preconditions.checkNotNull(lifecycle);
        return this.stateMachine.indexOf(lifecycle);
    }
}
