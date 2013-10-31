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
 * A JSON pattern layout to be used as input for logstash.
 * Each log message is a single JSON line for being easily parsed with logstash.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class LogstashPatternLayout extends PatternLayout {

    private static ObjectMapper mapper = createJsonObjectMapper();

    private static ObjectMapper createJsonObjectMapper() {
        ObjectMapper mapper = new ObjectMapper(new JsonFactory());
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, false);
        return mapper;
    }

    @Override
    public String format(LoggingEvent event) {
        final String original = super.format(event);
        final int jsonStart = original.indexOf("{");
        final int jsonEnd = original.lastIndexOf("}");
        final StringBuilder output = new StringBuilder();
        boolean fallback = false;
        if (jsonStart != -1 && jsonEnd != -1) {
            String json = original.substring(jsonStart, jsonEnd + 1);
            try {
                final Map<String, Object> parsed = mapper.readValue(json,
                        new TypeReference<HashMap<String, Object>>() {
                        });
                final String singleLineJson =
                        mapper.writeValueAsString(parsed);
                output.append(singleLineJson);
                output.append(System.getProperty("line.separator"));
            } catch (IOException e) {
                fallback = true;
            }
        }
        if (fallback) {
            output.append(original);
        }
        return output.toString();
    }

}
