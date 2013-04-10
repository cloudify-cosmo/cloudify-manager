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
package org.cloudifysource.cosmo.state;

import java.net.URI;

/**
 * Java interface for writing values to the kvstore.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public interface StateWriter {

    /**
     * Sets the state of the specified id to the specified state, if the current state matches the specified etag.
     * If there is no match, an exception is raised
     * If there is no current state, then ifMatches must be {@link Etag#EMPTY}
     * @return the etag if the new state
     * @throws EtagPreconditionNotMetException - if etag does not match the latest in the kvstore
     */
    Etag put(URI id, Object state, Etag ifMatchHeader);
}
