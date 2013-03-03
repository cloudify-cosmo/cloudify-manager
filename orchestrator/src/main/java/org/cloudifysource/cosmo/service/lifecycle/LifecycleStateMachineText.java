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

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Text based representation of a state machine.
 * Examples: "a-->b"
 *           "a<--b"
 *           "a<>b"
 *           "a<-->b<->c"
 *           "a-->b a-->c"
 *           "a-->b,a-->c"
 *
 * For more examples see LifeCycleStateMachineTest.
 *
 * @author itaif
 * @since 0.1
 */
public class LifecycleStateMachineText {

    //look for a word, optional space, optional left arrow, optional dashes, right arrow,
    //and then another word with overlapping. Overlapping is required for parsing b in "a<-->b<-->c"
    //see: http://stackoverflow.com/questions/7760162/returning-overlapping-regular-expressions
    static final Pattern RIGHT_ARROW_PATTERN = Pattern.compile("(\\w+)\\s*<?-*>\\s*(?=(\\w+))");
    static final Pattern LEFT_ARROW_PATTERN = Pattern.compile("(\\w+)\\s*<-*>?\\s*(?=(\\w+))");
    static final Pattern SINGULAR_PATTERN = Pattern.compile("(\\w+)");

    private String stateMachine;

    //Deserialization cotr
    public LifecycleStateMachineText() {

    }

    public LifecycleStateMachineText(String stateMachine) {
        this.stateMachine = stateMachine;
    }

    public void parse(LifecycleStateMachine stateMachine) {
        parseRightArrow(stateMachine);
        parseLeftArrow(stateMachine);
        parseSingulars(stateMachine);
    }

    private void parseRightArrow(LifecycleStateMachine stateMachine) {
        Matcher matcher = RIGHT_ARROW_PATTERN.matcher(this.stateMachine);
        while (matcher.find()) {
            final LifecycleState fromLifecycle = new LifecycleState(matcher.group(1));
            final LifecycleState toLifecycle = new LifecycleState(matcher.group(2));
            stateMachine.addStateTransition(fromLifecycle, toLifecycle);
        }
    }

    private void parseLeftArrow(LifecycleStateMachine stateMachine) {
        Matcher matcher = LEFT_ARROW_PATTERN.matcher(this.stateMachine);
        while (matcher.find()) {
            final LifecycleState fromLifecycle = new LifecycleState(matcher.group(2));
            final LifecycleState toLifecycle = new LifecycleState(matcher.group(1));
            stateMachine.addStateTransition(fromLifecycle, toLifecycle);
        }
    }

    private void parseSingulars(LifecycleStateMachine stateMachine) {
        Matcher matcher = SINGULAR_PATTERN.matcher(this.stateMachine);
        while (matcher.find()) {
            final LifecycleState lifecycleState = new LifecycleState(matcher.group(1));
            stateMachine.addState(lifecycleState);
        }
    }

    public String getStateMachine() {
        return stateMachine;
    }

    public void setStateMachine(String stateMachine) {
        this.stateMachine = stateMachine;
    }
}

