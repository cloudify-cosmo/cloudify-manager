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
 *******************************************************************************/
package org.cloudifysource.cosmo.messaging;

import com.fasterxml.jackson.annotation.JsonTypeInfo.Id;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.jsontype.TypeIdResolver;
import com.fasterxml.jackson.databind.type.SimpleType;
import com.google.common.base.Preconditions;
import com.google.common.base.Supplier;
import com.google.common.base.Suppliers;
import com.google.common.collect.BiMap;

/**
 * A plugin for Jackson JSON Object Mapper that converts messages class
 * to "message" property in the serialized JSON.
 *
 * Handles classes that matches the regex 'org\.cloudifysource\.cosmo\..*\.messages\..*Message.class'
 *
 * @see MessageTypeId
 *
 * @author itaif
 * @since 0.1
 */
public class MessageTypeIdResolver implements TypeIdResolver {

    public static final String PACKAGE_REGEX_FILTER = "org\\.cloudifysource\\.cosmo\\..*\\.messages\\..*Message.class";

    private static Supplier<BiMap<String, Class<?>>> idResolver =
            Suppliers.memoize(new ReflectionMessageTypeSupplier(PACKAGE_REGEX_FILTER));

    /**
     * warms up the message class cache.
     */
    public static void warmUpClassPathCache() {
        idResolver.get();
    }

    private JavaType baseType;

    @Override
    public void init(JavaType baseType) {
        this.baseType = baseType;
    }

    @Override
    public String idFromValue(Object value) {
        String id = idResolver.get().inverse().get(value.getClass());
        Preconditions.checkArgument(id != null, "Cannot serialize class %s since it does not conform to the " +
                "regex pattern %s", value.getClass(), PACKAGE_REGEX_FILTER);
        return id;
    }

    @Override
    public String idFromValueAndType(Object value, Class<?> suggestedType) {
        return idFromValue(value);
    }

    @Override
    public String idFromBaseType() {
        Preconditions.checkState(baseType != null);
        return MessageTypeId.toMessageTypeId(baseType.getRawClass());
    }

    @Override
    public Id getMechanism() {
        return Id.CLASS;
    }

    @Override
    public JavaType typeFromId(String id) {
        Class<?> clazz = idResolver.get().get(id);
        Preconditions.checkArgument(clazz != null, "Cannot convert id %s into a class", id);
        return SimpleType.construct(clazz);
    }
}


