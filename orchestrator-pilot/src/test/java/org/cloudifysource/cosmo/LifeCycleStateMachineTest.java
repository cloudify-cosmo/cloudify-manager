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


import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachineText;
import org.testng.Assert;
import org.testng.annotations.Test;

/**
 * Unit tests for {@link org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine}.
 *
 * @author itaif
 * @since 0.1
 */
public class LifeCycleStateMachineTest {

    LifecycleStateMachine sm;

    @Test
    public void testSingularStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s1"));
        assertSingular(state("name_s1"));
    }

    private void assertSingular(LifecycleState s) {
        sm.setCurrentState(s);
        Assert.assertEquals(next(s), s);
    }

    @Test
    public void testBiSingularStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1 name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s1"));
        assertSingular(state("name_s1"));
        assertSingular(state("name_s2"));
    }

    @Test
    public void testOneWayStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1>name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        Assert.assertEquals(sm.getBeginState(), state("name_s1"));
        Assert.assertEquals(sm.getEndState(), state("name_s2"));
        Assert.assertEquals(next(state("name_s2")), state("name_s2"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertNull(next(state("name_s1")));
    }

    @Test
    public void testTwoWayStateMachineTwoDashes() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1<-->name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineSingleDash() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1<->name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineNoDash() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1<>name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineComma() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2,name_s2->name_s1"));
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineWhitespace() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2 name_s2->name_s1"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));
        assertTwoWayStateMachine(sm);
    }

    private void assertTwoWayStateMachine(LifecycleStateMachine sm) {
        sm.setCurrentState(state("name_s1"));
        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s1")), state("name_s1"));
    }

    @Test
    public void testLongStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2->name_s3"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));

        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s2"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertNull(next(state("name_s1")));

        sm.setCurrentState(state("name_s3"));
        Assert.assertNull(next(state("name_s1")));
        Assert.assertNull(next(state("name_s2")));
    }

    @Test
    public void testTwoWayLongStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1<->name_s2<->name_s3"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));

        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s2"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertEquals(next(state("name_s1")), state("name_s1"));

        sm.setCurrentState(state("name_s3"));
        Assert.assertEquals(next(state("name_s1")), state("name_s2"));
        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
    }

    @Test
    public void testSplitStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2->name_s3 name_s1->name_s4"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));

        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s2"));
        Assert.assertEquals(next(state("name_s4")), state("name_s4"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertNull(next(state("name_s4")));

        sm.setCurrentState(state("name_s3"));
        Assert.assertNull(next(state("name_s4")));

        sm.setCurrentState(state("name_s4"));
        Assert.assertNull(next(state("name_s1")));
        Assert.assertNull(next(state("name_s2")));
        Assert.assertNull(next(state("name_s3")));
    }

    @Test
    public void testJoinStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2->name_s3,name_s4->name_s3"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));

        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s2"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertNull(next(state("name_s4")));

        sm.setCurrentState(state("name_s3"));
        Assert.assertNull(next(state("name_s4")));

        sm.setCurrentState(state("name_s4"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertNull(next(state("name_s1")));
        Assert.assertNull(next(state("name_s2")));
    }

    @Test
    public void testRingStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1->name_s2->name_s3->name_s1"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));

        Assert.assertEquals(next(state("name_s2")), state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s2"));

        sm.setCurrentState(state("name_s2"));
        Assert.assertEquals(next(state("name_s3")), state("name_s3"));
        Assert.assertEquals(next(state("name_s1")), state("name_s3"));

        sm.setCurrentState(state("name_s3"));
        Assert.assertEquals(next(state("name_s1")), state("name_s1"));
        Assert.assertEquals(next(state("name_s2")), state("name_s1"));
    }

    @Test()
    public void testEndlessRingStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1<->name_s2,name_s3->name_s4"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s3"));
        Assert.assertNull(next(state("name_s3")));
    }

    @Test
    public void testBootstrapperStateMachine() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s3->name_s1<->name_s2"));
        sm.setBeginState(state("name_s1"));
        sm.setEndState(state("name_s2"));

        sm.setCurrentState(state("name_s3"));
        Assert.assertEquals(next(state("name_s2")), state("name_s1"));
    }

    @Test
    public void testIsState() {
        sm = new LifecycleStateMachine();
        sm.setLifecycleName(new LifecycleName("name"));
        sm.setText(new LifecycleStateMachineText("name_s1 name_s2"));
        sm.setBeginState(state("name_1"));
        sm.setEndState(state("name_2"));

        Assert.assertTrue(sm.isLifecycleBeginState());
        Assert.assertFalse(sm.isLifecycleEndState());

        sm.setCurrentState(sm.getEndState());
        Assert.assertFalse(sm.isLifecycleBeginState());
        Assert.assertTrue(sm.isLifecycleEndState());
    }

    private static LifecycleState state(String state) {
        return new LifecycleState(state);
    }

    private LifecycleState next(LifecycleState state) {
        return sm.getNextLifecycleState(state);
    }
}
