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

import com.google.common.base.Objects;
import com.google.common.collect.ImmutableList;

import java.util.List;

/**
 * TODO javadoc.
 *
 * @since 0.1
 * @author Dan Kilman
 */
class KeyValueCondition implements Condition {

    private final String key;
    private final Object value;

    public KeyValueCondition(String key, Object value) {
        this.key = key;
        this.value = value;
    }

    @Override
    public boolean applies(StateCacheSnapshot snapshot) {
        return Objects.equal(value, snapshot.get(key));
    }

    @Override
    public List<String> keysToLock() {
        return ImmutableList.of(key);
    }
}
