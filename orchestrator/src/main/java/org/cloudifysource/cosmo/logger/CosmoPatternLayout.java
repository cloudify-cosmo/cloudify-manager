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

package org.cloudifysource.cosmo.logger;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.apache.log4j.PatternLayout;
import org.apache.log4j.spi.LoggingEvent;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * A JSON pattern layout for Cosmo usages.
 * Each log message is a single JSON line for being easily parsed by logstash and others.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class CosmoPatternLayout extends PatternLayout {

    private static final ObjectMapper OBJECT_MAPPER = createJsonObjectMapper();

    private static ObjectMapper createJsonObjectMapper() {
        ObjectMapper mapper = new ObjectMapper(new JsonFactory());
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, false);
        return mapper;
    }

    @Override
    public String format(LoggingEvent event) {
        if (event.getProperties().containsKey("json")) {
            return String.format("%s%s", event.getProperties().get("json"), System.getProperty("line.separator"));
        }
        final Map<String, Object> eventMap = extractJsonFromLogMessage(event);
        if (eventMap != null) {
            try {
                return String.format("%s%s", convertObjectToJson(eventMap), System.getProperty("line.separator"));
            } catch (JsonProcessingException ignored) {
            }
        }
        return super.format(event);
    }

    /**
     * Extracts JSON content from a logging event and parses it into a Map.
     * @param event Logging event.
     * @return Parsed JSON as map or null if there's no JSON content.
     */
    public static Map<String, Object> extractJsonFromLogMessage(LoggingEvent event) {
        final String original = event.getMessage().toString();
        final int jsonStart = original.indexOf("{");
        final int jsonEnd = original.lastIndexOf("}");
        if (jsonStart != -1 && jsonEnd != -1) {
            try {
                String json = original.substring(jsonStart, jsonEnd + 1);
                return OBJECT_MAPPER.readValue(json,
                        new TypeReference<HashMap<String, Object>>() {
                        });
            } catch (IOException ignored) {
            }
        }
        return null;
    }

    /**
     * Converts the provided object to a JSON string.
     * @param obj The object.
     * @return JSON representation of the provided object.
     */
    public static String convertObjectToJson(Object obj) throws JsonProcessingException {
        return OBJECT_MAPPER.writeValueAsString(obj);
    }

}
