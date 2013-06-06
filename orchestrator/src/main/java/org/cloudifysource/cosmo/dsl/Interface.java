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

import com.google.common.collect.Lists;

import java.util.List;

/**
 * TODO write javadoc.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Interface implements Named {

    private String name;
    private String provider;
    private List<String> operations;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public List<String> getOperations() {
        return operations;
    }

    public void setOperations(List<String> operations) {
        this.operations = operations;
    }

    public void inheritPropertiesFrom(Interface other) {
        setProvider(other.getProvider());
        if (operations != null && other.getOperations() != null) {
            operations.addAll(other.getOperations());
        } else if (other.getOperations() != null) {
            operations = Lists.newArrayList(other.getOperations());
        }
    }

}
