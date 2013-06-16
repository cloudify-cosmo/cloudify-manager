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

package org.cloudifysource.cosmo.dsl.tree;

import java.net.URI;

/**
 * A DSL import container which holds the DSL's content and {@link URI}.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLImport {

    private String content;
    private URI uri;

    public DSLImport(String content, URI uri) {
        this.content = content;
        this.uri = uri;
    }

    public String getContent() {
        return content;
    }

    public URI getUri() {
        return uri;
    }
}
