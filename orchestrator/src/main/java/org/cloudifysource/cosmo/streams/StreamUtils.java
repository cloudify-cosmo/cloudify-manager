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
package org.cloudifysource.cosmo.streams;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonGenerationException;
import com.fasterxml.jackson.core.JsonParseException;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Set;

/**
 * A temporary placeholder for json manipulation related static methods.
 * Need to encapsulate in another class.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class StreamUtils {

    private StreamUtils() { }

    public static <T> T cloneElement(ObjectMapper mapper, T state) {

        @SuppressWarnings("unchecked")
        Class<? extends T> clazz = (Class<? extends T>) state.getClass();
        return (T) fromJson(mapper, toJson(mapper, state), clazz);
    }

    public static String toJson(ObjectMapper mapper, Object state) {
        try {
            String json = mapper.writeValueAsString(state);
            Preconditions.checkState(json.length() > 0);
            return json;
        } catch (JsonProcessingException e) {
            throw Throwables.propagate(e);
        }
    }

    public static <T> T fromJson(ObjectMapper mapper, String json, Class<? extends T> clazz) {
        try {
            Preconditions.checkArgument(json.length() > 0);
            return (T) mapper.readValue(json, clazz);
        } catch (JsonParseException e) {
            throw Throwables.propagate(e);
        } catch (JsonMappingException e) {
            throw Throwables.propagate(e);
        } catch (JsonGenerationException e) {
            throw Throwables.propagate(e);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    public static <T> boolean elementEquals(ObjectMapper mapper, T state1, T state2) {
        Preconditions.checkArgument(state1.getClass().equals(state2.getClass()));
        try {
            final String state1String = mapper.writeValueAsString(state1);
            final String state2String = mapper.writeValueAsString(state2);
            return state1String.equals(state2String);
        } catch (JsonGenerationException e) {
            throw Throwables.propagate(e);
        } catch (JsonMappingException e) {
            throw Throwables.propagate(e);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     * @return joined list of ids maintaining order, removing duplicates
     */
    public static Iterable<URI> concat(final Iterable<URI> ids1, final Iterable<URI> ids2) {
        return ImmutableSet.copyOf(Iterables.concat(ids1, ids2));
    }

    /**
     * @return old ids that are not in the newIds, maintaining order, removing duplicates.
     */
    public static Iterable<URI> diff(final Iterable<URI> oldIds, final Iterable<URI> newIds) {
        final Set<URI> idsToFilter = Sets.newHashSet(newIds);
        final Iterable<URI> diffWithDuplicates =
            Iterables.filter(oldIds, new Predicate<URI>() {

                @Override
                public boolean apply(URI id) {
                    return !idsToFilter.contains(id);
                }
            });
        return ImmutableSet.copyOf(diffWithDuplicates);
    }

    public static URI newURI(String uri) {
        try {
            return new URI(uri);
        } catch (final URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }

    public static URI fixSlash(URI id) {
        Preconditions.checkNotNull(id);
        String externalForm = id.toString();
        if (!externalForm.endsWith("/")) {
            if (!externalForm.substring(externalForm.lastIndexOf("/") + 1).startsWith("_")) {
                externalForm += "/";
            }
        }
        return StreamUtils.newURI(externalForm);
    }

    public static String fixSlash(String id) {
        Preconditions.checkNotNull(id);
        if (!id.endsWith("/")) {
            if (!id.substring(id.lastIndexOf("/") + 1).startsWith("_")) {
                id += "/";
            }
        }
        return id;
    }

    public static ObjectMapper newObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, true);
        return mapper;
    }
}
