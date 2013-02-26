package org.cloudifysource.cosmo;

import com.fasterxml.jackson.annotation.JsonIgnore;
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
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A state machine implementation.
 * @author itaif
 * @since 0.1
 */
public class LifecycleStateMachine {

    //Maps state into zero or more children states.
    private Map<String,Set<String>> indexedStateMachine = Maps.newLinkedHashMap();
    private String initialLifecycle;
    private String finalLifecycle;
    //text based description of the state machine (e.g. "a-->b,b-->c" )
    private String lifecycles;

    //look for a word, optional space, optional left arrow, optional dashes, right arrow,
    //and then another word with overlapping. Overlapping is required for parsing b in "a<-->b<-->c"
    //see: http://stackoverflow.com/questions/7760162/returning-overlapping-regular-expressions
    final Pattern rightArrowPattern = Pattern.compile("(\\w+)\\s*<?-*>\\s*(?=(\\w+))");
    final Pattern leftArrowPattern = Pattern.compile("(\\w+)\\s*<-*>?\\s*(?=(\\w+))");
    final Pattern singularPattern = Pattern.compile("(\\w+)");

    public LifecycleStateMachine() {
        //for backwards compat
    }

    /**
     * @param lifecycles - text based representation of state machine.
     *                     Examples: "a-->b"
     *                               "a<--b"
     *                               "a<-->b"
     *                               "a<-->b<-->c"
     *                               "a-->b a-->c"
     *                               "a-->b,a-->c"
     */
    public LifecycleStateMachine(String lifecycles) {
       this.lifecycles = lifecycles;
       parseRightArrow();
       parseLeftArrow();
       parseSingulars();
    }

    private void parseRightArrow() {
        Matcher matcher = rightArrowPattern.matcher(lifecycles);
        while (matcher.find()) {
            addStateTransition(matcher.group(1),matcher.group(2));
        }
    }

    private void parseLeftArrow() {
        Matcher matcher = leftArrowPattern.matcher(lifecycles);
        while (matcher.find()) {
            addStateTransition(matcher.group(2),matcher.group(1));
        }
    }

    private void parseSingulars() {
        Matcher matcher = singularPattern.matcher(lifecycles);
        while (matcher.find()) {
            addState(matcher.group(1));
        }
    }

    public void setInitialLifecycle(String initialLifecycle) {
        this.initialLifecycle = initialLifecycle;
    }

    public void setFinalLifecycle(String finalLifecycle) {
        this.finalLifecycle = finalLifecycle;
    }

    private void addStateTransition(String fromLifecycle, String toLifecycle) {
        Preconditions.checkNotNull(fromLifecycle);
        Preconditions.checkNotNull(toLifecycle);
        addState(fromLifecycle);
        addState(toLifecycle);
        indexedStateMachine.get(fromLifecycle).add(toLifecycle);

    }

    private void addState(String lifecycle) {
        if (!indexedStateMachine.containsKey(lifecycle)) {
            indexedStateMachine.put(lifecycle, Sets.<String>newLinkedHashSet());
        }
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
        if (indexedStateMachine.containsKey(currentLifecycle)) {
            //return findNextRecursive(currentLifecycle, desiredLifecycle, Sets.<String>newLinkedHashSet()).orNull();
            return findNext(currentLifecycle, desiredLifecycle).orNull();
        }
        return null;
    }

    public String getInitialLifecycle() {
        return initialLifecycle;
    }

    public String getFinalLifecycle() {
        return finalLifecycle;
    }

    /**
     * Finds the next state that would bring us closer from initial state
     * to the desired state.
     * @param initState - the initial state to walk the state machine
     * @param desiredState - the last state (stop condition)
     * @return the next step to walk on the state machine.
     */
    Optional<String> findNext(String initState, String desiredState) {

        Preconditions.checkNotNull(initState);
        Preconditions.checkNotNull(desiredState);

        if (initState.equals(desiredState)) {
            //edge case - already in desired state.
            return Optional.fromNullable(initState);
        }

        //used to prevent endless loops in traversing the state machine.
        final Set<String> visited = Sets.newLinkedHashSet();
        //stack to remember which parts we already scanned.
        final LinkedList<List<String>> childrenStack = Lists.newLinkedList();
        //inject children of initial state
        childrenStack.add(Lists.newArrayList(indexedStateMachine.get(initState)));

        while (true) {
            Preconditions.checkState(childrenStack.size() <= this.indexedStateMachine.size());
            if (childrenStack.isEmpty()) {
                // no more states to scan, no path exists.
                return Optional.absent();
            }
            final List<String> childs = Iterables.getLast(childrenStack);
            if (childs.isEmpty()) {
                //scanned all children did not find desired state,
                //backtracking ...
                childrenStack.removeLast();
                continue;
            }
            String currentState = childs.get(0);
            if (visited.contains(currentState)) {
                //loop - already scanned this child, ignore
                childs.remove(0);
                continue;
            }
            visited.add(currentState);

            if (currentState.equals(desiredState)) {
                // path to desired state exists, return first child
                return Optional.fromNullable(childrenStack.get(0).get(0));
            }

            // iterate over all children
            final Set<String> children = indexedStateMachine.get(currentState);
            childrenStack.add(Lists.newArrayList(children));
        }
    }
}
