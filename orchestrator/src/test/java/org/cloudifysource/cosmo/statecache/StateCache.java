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

import java.util.Map;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StateCache {

    private final Map<String, Object> cache;

    public StateCache(Map<String, Object> initialState) {
        this.cache = Maps.newHashMap(initialState);
    }

    public StateCache() {
        this(Maps.<String, Object>newHashMap());
    }

    public Object get(String key) {
        return cache.get(key);
    }

    public Object put(String key, Object value) {
        return cache.put(key, value);
    }

    public Map<String, Object> toMap() {
        return Maps.newHashMap(cache);
    }

    public void waitForState(final Object receiver, final Object context, final String key, final String value,
                             final StateChangeCallback callback) {
        new Thread() {
            @Override
            public void run() {
                try {
                    System.out.println("sleep 2 seconds");
                    Thread.sleep(2000);
                    callback.onStateChange(receiver, context, StateCache.this, toMap());
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        } .start();

    }

}
