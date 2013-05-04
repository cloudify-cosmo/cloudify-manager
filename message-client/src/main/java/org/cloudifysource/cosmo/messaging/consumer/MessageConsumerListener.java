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
package org.cloudifysource.cosmo.messaging.consumer;

import java.net.URI;

/**
 * Callback for received messages from the message broker.
 * @see MessageConsumer
 *
 * @param <T> The message type
 *
 * @author itaif
 * @since 0.1
 */
public interface MessageConsumerListener<T> {

    /**
     * Callback when a new message is received.
     */
    void onMessage(URI uri, T message);

    /**
     * Callback when any error occurs.
     */
    void onFailure(Throwable t);
}
