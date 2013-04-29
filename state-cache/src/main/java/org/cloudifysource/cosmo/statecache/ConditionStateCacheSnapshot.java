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

import java.util.Map;

/**
 * TODO javadoc.
 *
 * @since 0.1
 * @author Dan Kilman
 */
class ConditionStateCacheSnapshot implements StateCacheSnapshot {

    // all operations are synchronized by 'cacheMapLock'
    private final Map<String, Object> cache;
    private final Object cacheMapLock;

    public ConditionStateCacheSnapshot(Map<String, Object> cache, Object cacheMapLock) {
        this.cache = cache;
        this.cacheMapLock = cacheMapLock;
    }

    @Override
    public Object get(String key) {
        synchronized (cacheMapLock) {
            return cache.get(key);
        }
    }

    @Override
    public boolean containsKey(String key) {
        synchronized (cacheMapLock) {
            return cache.containsKey(key);
        }
    }

    @Override
    public ImmutableMap<String, Object> asMap() {
        throw new UnsupportedOperationException("condition snapshot cannot be viewed as an immutable map");
    }
}
