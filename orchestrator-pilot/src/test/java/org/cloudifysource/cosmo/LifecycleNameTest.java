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
import org.testng.Assert;
import org.testng.annotations.Test;

/**
 * Unit Tests for {@link org.cloudifysource.cosmo.service.lifecycle.LifecycleName}.
 * @author itaif
 * @since 0.1
 */
public class LifecycleNameTest {

    // TODO SSH add secondary name tests?

    @Test
    public void testValidName() {
        LifecycleName name = new LifecycleName();
        name.setName("x");
        Assert.assertEquals(name.getName(), "x");
        name.validateLifecycleStateName(new LifecycleState("x_y"));
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testValidNameInvalidState() {
        LifecycleName name = new LifecycleName();
        name.setName("x");
        Assert.assertEquals(name.getName(), "x");
        name.validateLifecycleStateName(new LifecycleState("z_y"));
    }

    @Test
    public void testFromLifecycleState() {
        final LifecycleState lifecycleState = new LifecycleState("x_y");
        final LifecycleName name = LifecycleName.fromLifecycleState(lifecycleState);
        Assert.assertEquals(name.getName(), "x");
        name.validateLifecycleStateName(lifecycleState);
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testValidateLifecycleStateName() {
        final LifecycleName name = new LifecycleName("x");
        Assert.assertEquals(name.getName(), "x");
        name.validateLifecycleStateName(new LifecycleState("x"));
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testFromInvalidLifecycleState() {
        final LifecycleState lifecycleState = new LifecycleState("xy");
        LifecycleName.fromLifecycleState(lifecycleState);
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testFromInvalidLifecycleStateWithDash() {
        final LifecycleState lifecycleState = new LifecycleState("x-y");
        LifecycleName.fromLifecycleState(lifecycleState);
    }

    @Test
    public void testLifeCycleNameWithUnderscore() {
        final LifecycleState lifecycleState = new LifecycleState("x_y_z");
        final LifecycleName name = LifecycleName.fromLifecycleState(lifecycleState);
        Assert.assertEquals(name.getName(), "x_y");
        name.validateLifecycleStateName(lifecycleState);
    }

    @Test
    public void testLifeCycleNameWithDash() {
        final LifecycleState lifecycleState = new LifecycleState("x-y_z");
        final LifecycleName name = LifecycleName.fromLifecycleState(lifecycleState);
        Assert.assertEquals(name.getName(), "x-y");
        name.validateLifecycleStateName(lifecycleState);
    }

    @Test
    public void testLifeCycleNameWithDashAndUnderscore() {
        final LifecycleState lifecycleState = new LifecycleState("y_x-y_z");
        final LifecycleName name = LifecycleName.fromLifecycleState(lifecycleState);
        Assert.assertEquals(name.getName(), "y_x-y");
        name.validateLifecycleStateName(lifecycleState);
    }

    @Test
    public void testLifeCycleComplexName() {
        final LifecycleState lifecycleState = new LifecycleState("abcd-e-f_g-hijklmnop");
        final LifecycleName name = LifecycleName.fromLifecycleState(lifecycleState);
        Assert.assertEquals(name.getName(), "abcd-e-f");
        name.validateLifecycleStateName(lifecycleState);
    }


}
