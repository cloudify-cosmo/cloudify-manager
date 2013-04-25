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

import com.google.common.collect.Maps;
import junit.framework.Assert;
import org.testng.annotations.Test;

import java.util.Map;
import java.util.Random;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 *
 * @since 0.1
 * @author Dan Kilman
 */
public class NamedLockProviderTest {

    private final Random random = new Random();

    private final NamedLockProvider namedLock = new NamedLockProvider();
    private final Map<ReentrantReadWriteLock, ReentrantReadWriteLock> locks = Maps.newConcurrentMap();
    private final Map<Integer, Integer> lockIDs = Maps.newConcurrentMap();

    private volatile boolean wait = true;
    private volatile boolean run = true;

    @Test
    public void test() throws Exception {
        int numberOfConcurrentClients = 10;
        LockProviderClient[] clients = new LockProviderClient[numberOfConcurrentClients];
        for (int i = 0; i < clients.length; i++) {
            clients[i] = new LockProviderClient();
            clients[i].start();
        }

        wait = false;

        Thread.sleep(100);

        run = false;

        for (int i = 0; i < clients.length; i++)
            clients[i].join();

        Assert.assertEquals("Unexpected number of locks created", lockIDs.size(), locks.size());
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    private class LockProviderClient extends Thread {
        @Override
        public void run() {
            while (wait) {

            }

            while (run) {
                int maxID = 500;
                int lockID = random.nextInt(maxID);
                ReentrantReadWriteLock lock = namedLock.forName("" + lockID);
                locks.put(lock, lock);
                lockIDs.put(lockID, lockID);
            }
        }
    }

}
