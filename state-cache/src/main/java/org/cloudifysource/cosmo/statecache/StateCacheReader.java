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
 * Exposes data consumption operations on the {@link StateCache}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public interface StateCacheReader {

    /**
     * @return An immutable copy of the state cache.
     */
    ImmutableMap<String, Object> snapshot();

    /**
     * @param receiver - ruote participant
     * @param context - ruote work item
     * @param key - the value to listen to
     * @param value - the exact value to wait for
     * @param callback - the method called when the condition is satisfied
     * @return callback UID, used in case the callback needs to be removed
     */
    String subscribeToKeyValueStateChanges(Object receiver,
                                           Object context,
                                           String key,
                                           Object value,
                                           StateChangeCallback callback);

    /**
     * Un-subscribe callback for state changes represented by the callback UID.
     * @param callbackUID - The return value of subscribeToKeyValueStateChanges.
     */
    void removeCallback(String callbackUID);
}
