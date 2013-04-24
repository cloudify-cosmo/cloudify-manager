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

import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;
import com.google.common.util.concurrent.MoreExecutors;

import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StateCache {

    private final ExecutorService executorService;
    private final Map<String, Object> cache;
    private final Map<Condition, Set<CallbackContext>> listeners;

    private StateCache(Map<String, Object> initialState, ExecutorService executorService) {
        this.executorService = executorService;
        this.cache = Maps.newHashMap(initialState);
        this.listeners = Maps.newHashMap();
    }

    public Object put(String key, Object value) {

        Object previous = cache.put(key, value);

        final Condition condition = new KeyValueCondition(key, value);
        final Set<CallbackContext> callbacks = listeners.get(condition);
        if (callbacks != null) {
            for (final CallbackContext callbackContext : callbacks) {
                submitStateChangeNotificationTask(callbackContext);
            }
            listeners.remove(condition);
        }

        return previous;
    }

    public Map<String, Object> toMap() {
        return Maps.newHashMap(cache);
    }

    public void waitForState(final Object receiver, final Object context, final String key, final Object value,
                             final StateChangeCallback callback) {
        Preconditions.checkNotNull(key);
        Preconditions.checkNotNull(value);

        CallbackContext callbackContext = new CallbackContext(receiver, context, callback);

        if (value.equals(cache.get(key))) {
            submitStateChangeNotificationTask(callbackContext);
            return;
        }

        Condition condition = new KeyValueCondition(key, value);
        Set<CallbackContext> conditionCallbacks = listeners.get(condition);
        if (conditionCallbacks == null) {
            conditionCallbacks = Sets.newHashSet();
        }
        conditionCallbacks.add(callbackContext);
        listeners.put(condition, conditionCallbacks);
    }

    private void submitStateChangeNotificationTask(final CallbackContext callbackContext) {
        executorService.submit(new Runnable() {
            @Override
            public void run() {
                System.out.println(Thread.currentThread().getId());
                callbackContext.getCallback().onStateChange(callbackContext.getReceiver(),
                        callbackContext.getContext(), StateCache.this, toMap());
            }
        });
    }

    public static class Builder {
        private ExecutorService executorService;
        private Map<String, Object> initialState;

        public StateCache build() {
            return new StateCache(
                initialState != null ? initialState : Collections.<String, Object>emptyMap(),
                executorService != null ? executorService : MoreExecutors.sameThreadExecutor()
            );
        }

        public StateCache.Builder initialState(Map<String, Object> initialState) {
            this.initialState = initialState;
            return this;
        }

        public StateCache.Builder executorService(ExecutorService executorService) {
            this.executorService = executorService;
            return this;
        }

    }

    private static class CallbackContext {

        private final Object receiver;
        private final Object context;
        private final StateChangeCallback callback;

        public CallbackContext(Object receiver, Object context, StateChangeCallback callback) {
            this.receiver = receiver;
            this.context = context;
            this.callback = callback;
        }

        public StateChangeCallback getCallback() {
            return callback;
        }

        public Object getContext() {
            return context;
        }

        public Object getReceiver() {
            return receiver;
        }
    }

    private interface Condition { }

    private static class KeyValueCondition implements Condition {

        private final String key;
        private final Object value;

        public KeyValueCondition(String key, Object value) {
            this.key = key;
            this.value = value;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;

            KeyValueCondition that = (KeyValueCondition) o;

            if (key != null ? !key.equals(that.key) : that.key != null) return false;
            if (value != null ? !value.equals(that.value) : that.value != null) return false;

            return true;
        }

        @Override
        public int hashCode() {
            int result = key != null ? key.hashCode() : 0;
            result = 31 * result + (value != null ? value.hashCode() : 0);
            return result;
        }
    }

}
