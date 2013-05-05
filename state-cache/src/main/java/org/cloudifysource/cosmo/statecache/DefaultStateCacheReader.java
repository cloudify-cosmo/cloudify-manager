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

/**
 * A {@link StateCacheReader} implementation that delegates all operations to an underlying {@link StateCache}.
 * TODO: What is our naming convention: StateCacheReaderImpl, DefaultStateCacheReader, else?
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DefaultStateCacheReader implements StateCacheReader {

    private final StateCache stateCache;

    public DefaultStateCacheReader(StateCache stateCache) {
        this.stateCache = stateCache;
    }

    @Override
    public ImmutableMap<String, Object> snapshot() {
        return stateCache.snapshot();
    }

    @Override
    public String subscribeToKeyValueStateChanges(Object receiver, Object context, String key, Object value,
                                                  StateChangeCallback callback) {
        return stateCache.subscribeToKeyValueStateChanges(receiver, context, key, value, callback);
    }

    @Override
    public String subscribeToKeyValueStateChanges(Object reciever, Object context, String key,
                                                  StateChangeCallback stateChangeCallback) {
        return stateCache.subscribeToKeyValueStateChanges(reciever, context, key, stateChangeCallback);
    }

    @Override
    public void removeCallback(String callbackUID) {
        stateCache.removeCallback(callbackUID);
    }
}

