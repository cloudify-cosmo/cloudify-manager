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

package org.cloudifysource.cosmo.statecache;

import com.google.common.collect.ImmutableMap;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import java.util.Collections;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StateCacheTest {

    private StateCache stateCache;

    @BeforeMethod
    public void before() {
        stateCache = new StateCache.Builder()
                .build();
    }

    @AfterMethod(alwaysRun = true)
    public void after() {
        if (stateCache != null) {
            stateCache.close();
        }
    }

    @Test
    public void testInitialState() {
        stateCache.close();
        String key = "key";
        Object value = "value";
        stateCache = new StateCache.Builder().initialState(ImmutableMap.<String, Object>builder().put(key,
                value).build()).build();
        Object stateCacheValue = stateCache.snapshot().get(key);
        Assert.assertEquals(stateCacheValue, value);
    }

    @Test
    public void testPut() {
        String key = "key";
        Object value = "value";
        stateCache.put(key, value);
        Object stateCacheValue = stateCache.snapshot().get(key);
        Assert.assertEquals(stateCacheValue, value);
        value = "newValue";
        stateCache.put(key, value);
        stateCacheValue = stateCache.snapshot().get(key);
        Assert.assertEquals(stateCacheValue, value);
    }

    @Test
    public void testSnapshotContains() {
        String key = "key";
        Object value = "value";
        Assert.assertFalse(stateCache.snapshot().containsKey(key));
        stateCache.put(key, value);
        Assert.assertTrue(stateCache.snapshot().containsKey(key));
    }

    @Test
    public void testSnapshotGet() {
        String key = "key";
        Object value = "value";
        Assert.assertNull(stateCache.snapshot().get(key));
        stateCache.put(key, value);
        Assert.assertEquals(stateCache.snapshot().get(key), value);
    }

    @Test
    public void testSnapshotAsMap() {
        Assert.assertEquals(stateCache.snapshot().asMap(), Collections.emptyMap());
        String key = "key";
        Object value = "value";
        stateCache.put(key, value);
        Assert.assertEquals(stateCache.snapshot().asMap(), ImmutableMap.<String, Object>builder().put(key,
                value).build());
    }

    @Test
    public void testWaitForKeyValueState() throws InterruptedException {
        final CountDownLatch callbackCalledLatch = new CountDownLatch(1);
        final AtomicBoolean stateChangedProperly = new AtomicBoolean(false);
        final Object reciever = new Object();
        final Object context = new Object();
        final String key = "key";
        final Object value = "value";
        stateCache.waitForKeyValueState(reciever, context, key, value, new StateChangeCallback() {
            public void onStateChange(Object receiverParam, Object contextParam, StateCache cache,
                                      ImmutableMap<String, Object> newSnapshot) {
                boolean valid;
                valid = (receiverParam == reciever);
                valid &= (contextParam == context);
                valid &= (value.equals(newSnapshot.get(key)));
                stateChangedProperly.set(valid);
                callbackCalledLatch.countDown();
            }
        });

        Thread.sleep(100);

        Assert.assertEquals(callbackCalledLatch.getCount(), 1);

        stateCache.put(key, value);

        Assert.assertTrue(callbackCalledLatch.await(5, TimeUnit.SECONDS));
        Assert.assertTrue(stateChangedProperly.get());
    }

    @Test(dependsOnMethods = "testWaitForKeyValueState")
    public void testWaitForKeyValueStateIsRemoved() throws InterruptedException {
        final String key = "key";
        final Object value = "value";
        final CountDownLatch callbackCalledLatch = new CountDownLatch(1);
        final CountDownLatch callbackCalledAgainLatch = new CountDownLatch(1);
        stateCache.waitForKeyValueState(null, null, key, value, new StateChangeCallback() {
            public void onStateChange(Object receiverParam, Object contextParam, StateCache cache,
                                      ImmutableMap<String, Object> newSnapshot) {
                if (callbackCalledLatch.getCount() > 0) {
                    callbackCalledLatch.countDown();
                    return;
                }
                callbackCalledAgainLatch.countDown();
            }
        });

        stateCache.put(key, value);
        Assert.assertTrue(callbackCalledLatch.await(5, TimeUnit.SECONDS));
        stateCache.put(key, value);
        Assert.assertFalse(callbackCalledAgainLatch.await(100, TimeUnit.MILLISECONDS));
    }

    @Test(dependsOnMethods = "testWaitForKeyValueState")
    public void testRemoveCallback() throws InterruptedException {
        final String key = "key";
        final Object value = "value";
        final CountDownLatch callbackCalledLatch = new CountDownLatch(1);
        String callbackUID = stateCache.waitForKeyValueState(null, null, key, value, new StateChangeCallback() {
            public void onStateChange(Object receiverParam, Object contextParam, StateCache cache,
                                      ImmutableMap<String, Object> newSnapshot) {
                callbackCalledLatch.countDown();
            }
        });
        stateCache.removeCallback(callbackUID);
        stateCache.put(key, value);
        Assert.assertFalse(callbackCalledLatch.await(100, TimeUnit.MILLISECONDS));
    }

}
