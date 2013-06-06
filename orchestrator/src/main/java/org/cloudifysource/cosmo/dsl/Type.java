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

import java.util.Map;

/**
 * TODO write javadoc.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Type implements Named {

    public static final String ROOT_NODE_TYPE_NAME = "node";
    public static final Type ROOT_NODE_TYPE = initRootNodeType();

    private static Type initRootNodeType() {
        Type root = new Type();
        root.setName(ROOT_NODE_TYPE_NAME);
        return root;
    }

    private String name;
    // denotes parent type
    private String type;
    private Map<String, Interface> interfaces;
    // TODO DSL should be string -> object
    private Map<String, String> properties;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public Map<String, Interface> getInterfaces() {
        return interfaces;
    }

    public void setInterfaces(Map<String, Interface> interfaces) {
        this.interfaces = interfaces;
    }

    public Map<String, String> getProperties() {
        return properties;
    }

    public void setProperties(Map<String, String> properties) {
        this.properties = properties;
    }

    public void inheritPropertiesFrom(Type other) {
        if (other.getInterfaces() != null) {
            if (interfaces == null) {
                interfaces = Maps.newHashMap();
            }
            for (Map.Entry<String, Interface> entry : other.getInterfaces().entrySet()) {
                String otherInterfaceName = entry.getKey();
                Interface otherInterface = entry.getValue();
                if (interfaces.containsKey(otherInterfaceName)) {
                    Interface theInterface = interfaces.get(otherInterfaceName);
                    theInterface.inheritPropertiesFrom(otherInterface);
                } else {
                    Interface theInterface = new Interface();
                    theInterface.setName(otherInterfaceName);
                    theInterface.inheritPropertiesFrom(otherInterface);
                    interfaces.put(otherInterfaceName, theInterface);
                }
            }
        }

        if (properties != null && other.getProperties() != null) {
            properties.putAll(other.getProperties());
        } else if (other.getProperties() != null) {
            this.properties = Maps.newHashMap(other.getProperties());
        }

    }

}
