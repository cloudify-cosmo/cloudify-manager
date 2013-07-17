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
import org.cloudifysource.cosmo.statecache.StateCache;
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
 * Updates the {@link StateCache} with events received from Riemann.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class StateCacheFeeder {
    protected final Logger logger = LoggerFactory.getLogger(this.getClass());

    private final StateCache stateCache;
    private final RiemannPubSubConnection connection;

    public StateCacheFeeder(final RiemannPubSubClient riemannClient,
                            final RiemannEventObjectMapper objectMapper,
                            final StateCache stateCache,
                            final int numberOfConnectionAttempts,
                            final int sleepBeforeConnectionAttemptMilliseconds) {

        this.stateCache = stateCache;
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
                    // TODO: filter by event
                    if (event.getService().equals("events/sec") || event.getState() == null) {
                        //Filter out "events/sec" events
                        return;
                    }
                    final String resourceId = event.getHost();
                    Preconditions.checkNotNull(resourceId, "RiemannEvent host field cannot be null");
                    StateCacheFeeder.this.stateCache.put(resourceId, event.getService(), event.getState());
                } catch (IOException e) {
                    logger.warn(StateCacheLogDescription.MESSAGE_CONSUMER_ERROR, e);
                    throw Throwables.propagate(e);
                }
            }

            //TODO: See https://github.com/mgodave/riemann-client/issues/2
            //@Override
            //public void onFailure(Throwable t) {
            //RealTimeStateCache.this.messageConsumerFailure(t);
            //}

        };
    }


    private String queryString() {
        //TODO: Filter only processed events
        final String allEvents = "true";
        return allEvents;
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
