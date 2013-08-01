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

import static java.lang.Thread.sleep;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RiemannEventsLogger {
    protected final Logger logger = LoggerFactory.getLogger(this.getClass());

    private final RiemannPubSubConnection connection;

    public RiemannEventsLogger(final RiemannPubSubClient riemannClient,
                               final RiemannEventObjectMapper objectMapper,
                               final int numberOfConnectionAttempts,
                               final int sleepBeforeConnectionAttemptMilliseconds) {
        final QueryResultListener queryResultListener = queryResultListener(objectMapper);
        this.connection = connect(
                riemannClient,
                numberOfConnectionAttempts, sleepBeforeConnectionAttemptMilliseconds,
                queryResultListener);
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
                    logger.debug("[event] host={}, service={}, state={}, description={}",
                            event.getHost(),
                            event.getService(),
                            event.getState(),
                            event.getDescription());
                } catch (IOException e) {
                    logger.warn(StateCacheLogDescription.MESSAGE_CONSUMER_ERROR, e);
                    throw Throwables.propagate(e);
                }
            }
        };
    }

    private String queryString() {
        return "tagged \"cosmo\"";
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
