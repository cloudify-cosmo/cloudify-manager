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

import com.fasterxml.jackson.core.JsonProcessingException;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import org.apache.log4j.AppenderSkeleton;
import org.apache.log4j.FileAppender;
import org.apache.log4j.Level;
import org.apache.log4j.spi.LoggingEvent;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Timestamp;
import java.util.Map;

/**
 * Log4j Appender for writing each workflow logs to a different file according to the workflow id.
 *
 * @author Idan Moyal
 * @since 0.3
 */
public class CosmoBlueprintsFileAppender extends AppenderSkeleton {

    private Path path;
    private Map<String, FileAppender> appenders = Maps.newHashMap();

    public CosmoBlueprintsFileAppender() {
    }

    public CosmoBlueprintsFileAppender(Path path) {
        this();
        setPath(path.toString());
    }

    /**
     * Sets the path where log files will be stored in.
     * @param path Path as string.
     */
    public void setPath(String path) {
        this.path = Paths.get(path);
    }

    @Override
    protected void append(LoggingEvent event) {
        final Map<String, Object> objectMap = CosmoPatternLayout.extractJsonFromLogMessage(event);
        if (objectMap == null) {
            return;
        }
        final String loggingContext = extractLoggingContext(objectMap);
        if (StringUtils.hasLength(loggingContext)) {
            FileAppender appender = getFileAppender(loggingContext);
            try {
                objectMap.put("timestamp", new Timestamp(event.getTimeStamp()).toString());
                event.setProperty("json", CosmoPatternLayout.convertObjectToJson(objectMap));
                appender.append(event);
            } catch (JsonProcessingException ignored) {
            }
        }
    }

    private String extractLoggingContext(Map<String, Object> map) {
        if (map.containsKey("deployment_id")) {
            return map.get("deployment_id").toString();
        }
        if (map.containsKey("app")) {
            return map.get("app").toString();
        }
        return null;
    }

    private FileAppender getFileAppender(String name) {
        FileAppender appender = appenders.get(name);
        if (appender == null) {
            appender = createFileAppender(name);
            appenders.put(name, appender);
        }
        return appender;
    }

    private FileAppender createFileAppender(String name) {
        try {
            Path filePath = Paths.get(path.toString(), String.format("%s.log", name));
            FileAppender appender = new FileAppender(new CosmoPatternLayout(), filePath.toString());
            appender.setName(name);
            appender.setThreshold(Level.DEBUG);
            return appender;
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    @Override
    public void close() {
        for (FileAppender fileAppender : appenders.values()) {
            fileAppender.close();
        }
    }

    @Override
    public boolean requiresLayout() {
        return false;
    }
}
