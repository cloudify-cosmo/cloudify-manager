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

import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.statecache.config.TestConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
@ContextConfiguration(classes = { StateCacheTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class StateCacheTest extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({
            StateCacheConfig.class
    })
    static class Config extends TestConfig {
    }

    @Inject
    private StateCache stateCache;

    @Test
    public void testPut() {
        final String resourceId = "resource";
        final String property = "property";
        final String value = "value";
        stateCache.put(resourceId, property, value);
    }

    @Test
    public void testListenerResourceIdEventAfterPut() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final String resourceId2 = "resource2";
        final String property2 = "property2";
        final String value2 = "value2";
        final AtomicReference<StateCacheSnapshot> eventValue = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        stateCache.put(resourceId1, property1, value1);
        stateCache.put(resourceId2, property2, value2);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {
                eventValue.set(snapshot);
                latch.countDown();
                return false;
            }
        };
        stateCache.subscribe(resourceId1, listener);
        assertThat(latch.await(3, TimeUnit.SECONDS)).isTrue();
        assertThat(eventValue.get().getProperty(resourceId1, property1)).isEqualTo(value1);
        assertThat(eventValue.get().getProperty(resourceId2, property2)).isEqualTo(value2);
    }

    @Test
    public void testListenerResourceIdBeforeAfterPut() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final String resourceId2 = "resource2";
        final String property2 = "property2";
        final String value2 = "value2";
        final AtomicReference<StateCacheSnapshot> eventValue = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        stateCache.put(resourceId2, property2, value2);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {
                eventValue.set(snapshot);
                latch.countDown();
                return false;
            }
        };
        stateCache.subscribe(resourceId1, listener);

        assertThat(latch.await(50, TimeUnit.MILLISECONDS)).isFalse();

        stateCache.put(resourceId1, property1, value1);

        assertThat(latch.await(3, TimeUnit.SECONDS)).isTrue();
        assertThat(eventValue.get().getProperty(resourceId1, property1)).isEqualTo(value1);
        assertThat(eventValue.get().getProperty(resourceId2, property2)).isEqualTo(value2);
    }

    @Test
    public void testListenerRemovedResourceIdEventAfterPut() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final CountDownLatch latch = new CountDownLatch(2);
        stateCache.put(resourceId1, property1, value1);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {

                latch.countDown();
                return true;
            }
        };
        stateCache.subscribe(resourceId1, listener);
        Thread.sleep(50);
        assertThat(latch.getCount()).isEqualTo(1);
        stateCache.put(resourceId1, property1, value1);
        assertThat(latch.await(50, TimeUnit.MILLISECONDS)).isFalse();
    }

    @Test
    public void testListenerRemovedResourceIdEventBeforePut() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final CountDownLatch latch = new CountDownLatch(2);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {

                latch.countDown();
                return true;
            }
        };
        stateCache.subscribe(resourceId1, listener);
        stateCache.put(resourceId1, property1, value1);
        Thread.sleep(50);
        assertThat(latch.getCount()).isEqualTo(1);
        stateCache.put(resourceId1, property1, value1);
        assertThat(latch.await(50, TimeUnit.MILLISECONDS)).isFalse();
    }

    @Test
    public void testListenerThrowsExceptionIsRemoved() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final CountDownLatch latch = new CountDownLatch(2);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {

                latch.countDown();
                throw new RuntimeException();
            }
        };
        stateCache.subscribe(resourceId1, listener);
        stateCache.put(resourceId1, property1, value1);
        Thread.sleep(50);
        assertThat(latch.getCount()).isEqualTo(1);
        stateCache.put(resourceId1, property1, value1);
        assertThat(latch.await(50, TimeUnit.MILLISECONDS)).isFalse();
    }

    @Test
    public void testRemoveListener() throws InterruptedException {
        final String resourceId1 = "resource1";
        final String property1 = "property1";
        final String value1 = "value1";
        final CountDownLatch latch = new CountDownLatch(1);
        StateCacheListener listener = new StateCacheListener() {
            @Override
            public boolean onResourceStateChange(StateCacheSnapshot snapshot) {

                latch.countDown();
                return false;
            }
        };
        final String id = stateCache.subscribe(resourceId1, listener);
        stateCache.removeSubscription(resourceId1, id);
        stateCache.put(resourceId1, property1, value1);
        assertThat(latch.await(50, TimeUnit.MILLISECONDS)).isFalse();
    }
}
