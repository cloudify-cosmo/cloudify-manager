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
package org.cloudifysource.cosmo.messaging;

import com.google.common.base.Preconditions;
import com.google.common.base.Supplier;
import com.google.common.collect.BiMap;
import com.google.common.collect.HashBiMap;
import com.google.common.collect.Iterables;
import org.reflections.ReflectionUtils;
import org.reflections.Reflections;
import org.reflections.scanners.TypesScanner;
import org.reflections.util.ClasspathHelper;
import org.reflections.util.ConfigurationBuilder;
import org.reflections.util.FilterBuilder;

import java.net.URL;
import java.util.Collection;
import java.util.Set;

/**
 * Uses reflection to detect all message classes.
 *
 * @author itaif
 * @since 0.1
 */
public class ReflectionMessageTypeSupplier implements Supplier<BiMap<String, Class<?>>> {

    private final FilterBuilder cosmoMessagesFilter;

    public ReflectionMessageTypeSupplier(String packageRegexFilter) {
        cosmoMessagesFilter = new FilterBuilder().include(packageRegexFilter);
    }

    @Override
    public BiMap<String, Class<?>> get() {

        //see: http://code.google.com/p/reflections/issues/detail?id=122
        final Set<URL> urls = ClasspathHelper.forClassLoader();
        final Reflections reflections = new Reflections(
                new ConfigurationBuilder()
                        .filterInputsBy(cosmoMessagesFilter)
                        .addUrls(urls)
                        .setScanners(new TypesScanner().filterResultsBy(cosmoMessagesFilter)));

        final Set<Class<?>> t = reflections.getSubTypesOf(Object.class);
        final Collection<String> classNames =
                Iterables.getOnlyElement(reflections.getStore().getStoreMap().values()).values();
        final Iterable<Class<?>> messageTypes = ReflectionUtils.forNames(classNames, ClasspathHelper.classLoaders());
        BiMap<String, Class<?>> idResolver = HashBiMap.create();
        for (final Class<?> messageType : messageTypes) {
            registerType(messageType, idResolver);
        }

        return idResolver;
    }

    private void registerType(Class<?> clazz, BiMap<String, Class<?>> idResolver) {
        Preconditions.checkNotNull(clazz);

        final String id = MessageTypeId.toMessageTypeId(clazz);
        final Class<?> registeredClass = idResolver.get(id);

        if (registeredClass == null) {
            idResolver.put(id, clazz);
        } else {
            Preconditions.checkArgument(
                    registeredClass.equals(clazz),
                    "Cannot register type %s since it conflicts with %s",
                    clazz.getName(), registeredClass.getName());
        }
    }
}
