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

package org.cloudifysource.cosmo.dsl;

import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

import java.net.URI;
import java.util.Map;
import java.util.Set;

/**
 * Contains context used during the imports phase of the {@link DSLProcessor}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ImportContext {

    private final Map<String, String> aliasMappings = Maps.newHashMap();
    private final Set<URI> imports = Sets.newHashSet();
    private final URI baseUri;
    private URI contextUri;

    public ImportContext(URI baseUri) {
        this.baseUri = baseUri;
    }

    public void addImport(URI importUri) {
        imports.add(importUri);
    }

    public boolean isImported(URI importUri) {
        return imports.contains(importUri);
    }

    public URI getBaseUri() {
        return baseUri;
    }

    public URI getContextUri() {
        return contextUri;
    }

    public void setContextUri(URI contextUri) {
        this.contextUri = contextUri;
    }

    public String getMapping(String alias) {
        String mapping = aliasMappings.get(alias);
        return mapping != null ? mapping : alias;
    }

    public void addMapping(Map<String, String> aliasMappings) {
        this.aliasMappings.putAll(aliasMappings);
    }

}
