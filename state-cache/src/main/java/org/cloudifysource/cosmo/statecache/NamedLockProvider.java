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

import com.google.common.cache.CacheBuilder;
import com.google.common.cache.CacheLoader;
import com.google.common.cache.LoadingCache;

import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 *
 * Provides a thread safe name based lock interface for getting a shared lock instance based on its name.
 *
 * @since 0.1
 * @author Dan Kilman
 */
public class NamedLockProvider {

    private final LoadingCache<String, ReentrantReadWriteLock> lockCache;

    public NamedLockProvider() {
        lockCache = CacheBuilder.newBuilder().build(new CacheLoader<String, ReentrantReadWriteLock>() {
            public ReentrantReadWriteLock load(String name) {
                return new ReentrantReadWriteLock();
            }
        });
    }

    /**
     * @param name The name of the lock to get
     * @return The shared {@link java.util.concurrent.locks.ReentrantReadWriteLock} matching the provided name.
     * One is created if it doesn't already exist.
     * Note that the returned {@link java.util.concurrent.locks.ReentrantReadWriteLock}
     *   should still be aquired and released by the client
     * calling this method.
     */
    public ReentrantReadWriteLock forName(String name) {
        return lockCache.getUnchecked(name);
    }
}
