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

import java.io.Serializable;

/**
 * A state cache properties value wrapper.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class StateCacheValue implements Serializable {

    private static final long serialVersionUID = 1L;
    private String state;
    private String description;

    public StateCacheValue(String state) {
        this(state, null);
    }

    public StateCacheValue(String state, String description) {
        this.state = state;
        this.description = description;
    }

    public String getState() {
        return state;
    }

    public String getDescription() {
        return description;
    }
}
