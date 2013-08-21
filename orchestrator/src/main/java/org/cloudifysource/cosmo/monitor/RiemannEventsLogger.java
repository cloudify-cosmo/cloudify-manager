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

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.statecache.StateCacheLogDescription;
import org.jboss.netty.channel.ChannelException;
import org.robobninjas.riemann.json.RiemannEvent;
import org.robobninjas.riemann.json.RiemannEventObjectMapper;
import org.robotninjas.riemann.pubsub.QueryResultListener;
import org.robotninjas.riemann.pubsub.RiemannPubSubClient;
import org.robotninjas.riemann.pubsub.RiemannPubSubConnection;

import java.io.IOException;
import java.net.URISyntaxException;
import java.util.HashMap;
import java.util.Map;
import java.util.HashMap;
import java.util.Map;

import static java.lang.Thread.sleep;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RiemannEventsLogger {

    private static final Logger PLUGINS_LOGGER = LoggerFactory.getLogger("COSMO.PLUGIN");
    protected final Logger logger = LoggerFactory.getLogger(this.getClass());

    protected final Logger userOutputLogger = LoggerFactory.getLogger("COSMO");

    private static final String COSMO_LOG_TAG = "cosmo-log";
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private final RiemannPubSubConnection connection;
    private final RiemannPropertyPlaceHolderHelper propertyPlaceHolderHelper;

    public RiemannEventsLogger(final RiemannPubSubClient riemannClient,
                               final RiemannEventObjectMapper objectMapper,
                               final int numberOfConnectionAttempts,
                               final int sleepBeforeConnectionAttemptMilliseconds,
                               RiemannPropertyPlaceHolderHelper propertyPlaceHolderHelper) {
        final QueryResultListener queryResultListener = queryResultListener(objectMapper);
        this.connection = connect(
                riemannClient,
                numberOfConnectionAttempts, sleepBeforeConnectionAttemptMilliseconds,
                queryResultListener);
        this.propertyPlaceHolderHelper = propertyPlaceHolderHelper;


    }

    private RiemannPubSubConnection connect(
            RiemannPubSubClient riemannClient,
            int numberOfConnectionAttempts, int sleepBeforeConnectionAttemptMilliseconds,
            QueryResultListener queryResultListener) {

        ChannelException lastException = null;
        for (int i = 1; i <= numberOfConnectionAttempts; i++) {
            try {
                boolean subscribe = true;
                logger.debug("Attempt {} to connect with Riemann", i);
                return riemannClient.makeConnection(queryString(), subscribe, queryResultListener);

            } catch (org.jboss.netty.channel.ChannelException e) {
                lastException = e;
                if (i < numberOfConnectionAttempts) {
                    try {
                        sleep(sleepBeforeConnectionAttemptMilliseconds);
                    } catch (InterruptedException ie) {
                        throw Throwables.propagate(ie);
                    }
                }
            } catch (InterruptedException | URISyntaxException e) {
                throw Throwables.propagate(e);
            }
        }
        throw lastException;
    }

    private QueryResultListener queryResultListener(final RiemannEventObjectMapper objectMapper) {
        return new QueryResultListener() {
            @Override
            public void handleResult(String result) {
                try {
                    final RiemannEvent event = objectMapper.readEvent(result);
                    if (event.getService().equals("events/sec") || event.getState() == null) {
                        return;
                    }
                    Preconditions.checkNotNull(event.getHost(), "RiemannEvent host field cannot be null");

                    // log raw riemann event

                    logger.debug("[event] host={}, service={}, state={}, metric={}, description={}",
                            event.getHost(),
                            event.getService(),
                            event.getState(),
                            event.getMetric(),
                            event.getDescription());

                    // construct a pretty event to be logged to the user

                    Map<String, Object> description = objectMapper.readValue(event.getDescription(),
                            new TypeReference<HashMap<String, Object>>() {
                            });

                    String nodeId = (String) description.get("node_id");

                    String[] fullNodeId = nodeId.split("\\.");
                    String simpleNodeName = fullNodeId[1];
                    String simpleAppName = fullNodeId[0];

                    String policy = (String) description.get("policy");
                    String message = propertyPlaceHolderHelper.replace((String) description.get("message"), event);

                    userOutputLogger.debug("[monitor] - {" +
                            "'policy'=>'{}', 'app'=>'{}', " +
                            "'node'=>'{}'," +
                            "'message'=>'{}'}",
                            policy, simpleAppName, simpleNodeName, message);


                    if (event.getTags() != null && event.getTags().contains(COSMO_LOG_TAG)) {
                        final Map<?, ?> description = OBJECT_MAPPER.readValue(
                                event.getDescription(),
                                HashMap.class);
                        if (description.containsKey("log_record")) {
                            final Map<?, ?> logRecord = (Map<?, ?>) description.get("log_record");
                            final String message = logRecord.get("message").toString();
                            final String name = extractPluginName(logRecord.get("name").toString());
                            final String level = logRecord.get("level").toString();
                            switch (level) {
                                default:
                                case "INFO":
                                    PLUGINS_LOGGER.info(RiemannEventsLogDescription.PLUGIN_MESSAGE,
                                            level,
                                            name,
                                            message);
                                    break;
                                case "WARNING":
                                    PLUGINS_LOGGER.warn(RiemannEventsLogDescription.PLUGIN_MESSAGE,
                                            level,
                                            name,
                                            message);
                                    break;
                                case "ERROR":
                                case "CRITICAL":
                                    PLUGINS_LOGGER.error(RiemannEventsLogDescription.PLUGIN_MESSAGE,
                                            level,
                                            name,
                                            message);
                                    break;
                                case "DEBUG":
                                    PLUGINS_LOGGER.debug(RiemannEventsLogDescription.PLUGIN_MESSAGE,
                                            level,
                                            name,
                                            message);
                                    break;
                            }
                        }
                    } else {
                        logger.debug("[event] host={}, service={}, state={}, metric={}, description={}",
                                event.getHost(),
                                event.getService(),
                                event.getState(),
                                event.getMetric(),
                                event.getDescription());
                    }
                } catch (IOException e) {
                    logger.warn(StateCacheLogDescription.MESSAGE_CONSUMER_ERROR, e);
                    throw Throwables.propagate(e);
                }
            }

        };
    }

    private static String extractPluginName(String name) {
        String[] values = name.split("\\.");
        if (values.length > 1) {
            int last = values.length - 1;
            if (Objects.equal(values[last], "tasks")) {
                return values[last - 1];
            }
        }
        return name;
    }

    private String queryString() {
        return String.format("tagged \"cosmo\" or tagged \"%s\"", COSMO_LOG_TAG);
    }

    public void close() {
        if (connection != null) {
            try {
                connection.close();
            } catch (InterruptedException e) {
                throw Throwables.propagate(e);
            }
        }
    }

}
