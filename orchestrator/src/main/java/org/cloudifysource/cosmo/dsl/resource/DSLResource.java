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

package org.cloudifysource.cosmo.dsl.resource;

/**
 * A DSL resource container which holds the resource content and location.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLResource {

    private String content;
    private String location;

    public DSLResource(String content, String location) {
        this.content = content;
        this.location = location;
    }

    public String getContent() {
        return content;
    }

    public String getLocation() {
        return location;
    }
}
