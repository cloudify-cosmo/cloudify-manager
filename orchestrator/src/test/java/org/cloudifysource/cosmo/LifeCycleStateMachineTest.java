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


import org.testng.Assert;
import org.testng.annotations.Test;

public class LifeCycleStateMachineTest {

    @Test
    public void testEmptyStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("");
        Assert.assertNull(sm.getInitialLifecycle());
        Assert.assertNull(sm.getFinalLifecycle());
        Assert.assertNull(sm.getNextInstanceLifecycle("s1","s1"));
    }

    @Test
    public void testSingularStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1");
        assertSingular(sm, "s1");
    }

    private void assertSingular(LifecycleStateMachine sm, String s) {
        Assert.assertEquals(sm.getNextInstanceLifecycle(s, s), s);
    }

    @Test
    public void testBiSingularStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1 s2");
        assertSingular(sm, "s1");
        assertSingular(sm, "s2");
    }

    @Test
    public void testOneWayStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1>s2");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s2");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s2"),"s2");
        Assert.assertNull(sm.getNextInstanceLifecycle("s2", "s1"));
    }

    @Test
    public void testTwoWayStateMachineTwoDashes() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1<-->s2");
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineSingleDash() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1<->s2");
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineNoDash() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1<>s2");
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineComma() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2,s2->s1");
        assertTwoWayStateMachine(sm);
    }

    @Test
    public void testTwoWayStateMachineWhitespace() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2 s2->s1");
        assertTwoWayStateMachine(sm);
    }

    private void assertTwoWayStateMachine(LifecycleStateMachine sm) {
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s2"), "s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2", "s1"), "s1");
    }

    @Test
    public void testLongStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2->s3");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s2"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s3"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2","s3"),"s3");
        Assert.assertNull(sm.getNextInstanceLifecycle("s2", "s1"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s3","s1"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s3","s2"));
    }

    @Test
    public void testTwoWayLongStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1<->s2<->s3");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        //sm.addStateTransition("s1","s2");
        //sm.addStateTransition("s2","s3");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s2"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s3"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2","s3"),"s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2","s1"),"s1");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s3","s1"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s3","s2"),"s2");
    }

    @Test
    public void testSplitStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2->s3 s1->s4");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s2"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s3"), "s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2", "s3"), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s4"), "s4");
        Assert.assertNull(sm.getNextInstanceLifecycle("s4", "s1"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s4", "s2"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s4","s3"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s2","s4"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s3","s4"));
    }

    @Test
    public void testJoinStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2->s3,s4->s3");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s2"), "s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s3"), "s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2", "s3"), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s4","s3"),"s3");
        Assert.assertNull(sm.getNextInstanceLifecycle("s4", "s1"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s4", "s2"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s2", "s4"));
        Assert.assertNull(sm.getNextInstanceLifecycle("s3", "s4"));
    }

    @Test
    public void testRingStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1->s2->s3->s1");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        Assert.assertEquals(sm.getInitialLifecycle(), "s1");
        Assert.assertEquals(sm.getFinalLifecycle(), "s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1", "s2"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s1","s3"),"s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2","s3"),"s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s2","s1"),"s3");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s3","s1"),"s1");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s3","s2"),"s1");
    }

    @Test()
    public void testEndlessRingStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s1<->s2,s3->s4");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s3");
        Assert.assertNull(sm.getNextInstanceLifecycle("s1", "s3"));
    }

    @Test
    public void testBootstrapperStateMachine() {
        LifecycleStateMachine sm = new LifecycleStateMachine("s3->s1<->s2");
        sm.setInitialLifecycle("s1");
        sm.setFinalLifecycle("s2");
        Assert.assertEquals(sm.getNextInstanceLifecycle("s3","s2"),"s1");
    }
}
