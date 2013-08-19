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

package org.cloudifysource.cosmo.monitor;

import com.google.common.base.Function;
import com.google.common.collect.Maps;
import org.robobninjas.riemann.json.RiemannEvent;
import org.springframework.util.PropertyPlaceholderHelper;

import java.util.Map;
import java.util.Properties;

/**
 * Helper class for replacing placeholders with values from a reimann event.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
public class RiemannPropertyPlaceHolderHelper {

    private static final String[] PLACE_HOLDER_PROPS = {"metric.value", "state.value", "service.value", "host.value"};

    private Map<String, Function<RiemannEvent, Object>> placeHolderMappings;
    private PropertyPlaceholderHelper propertyPlaceholderHelper;

    public RiemannPropertyPlaceHolderHelper(String prefix, String suffix) {
        this.propertyPlaceholderHelper = new PropertyPlaceholderHelper(prefix, suffix);
        this.placeHolderMappings = createPlaceHolderMappings();
    }

    public String replace(String message, RiemannEvent event) {
        return propertyPlaceholderHelper.replacePlaceholders(message, createPropsFromMappings(event));

    }

    private Map<String, Function<RiemannEvent, Object>> createPlaceHolderMappings() {
        Map<String, Function<RiemannEvent, Object>> mappings = Maps.newHashMap();
        for (String placeholder : PLACE_HOLDER_PROPS) {
            mappings.put(placeholder, createFunction(placeholder));
        }
        return mappings;
    }

    private Properties createPropsFromMappings(RiemannEvent event) {
        Properties properties = new Properties();
        for (Map.Entry<String, Function<RiemannEvent, Object>> mapping : this.placeHolderMappings.entrySet()) {
            Object value = mapping.getValue().apply(event);
            if (value != null) {
                properties.put(mapping.getKey(), value.toString());
            }
        }
        return properties;
    }

    private Function<RiemannEvent, Object> createFunction(final String key) {
        return new Function<RiemannEvent, Object>() {

            @Override
            public Object apply(RiemannEvent input) {

                switch (key) {

                    case "metric.value":
                        return input.getMetric();
                    case "state.value":
                        return input.getState();
                    case "service.value":
                        return input.getService();
                    case "host.value":
                        return input.getHost();
                    default:
                        throw new IllegalStateException("Unsupported place holder '" + key + "'");
                }

            }
        };
    }
}
