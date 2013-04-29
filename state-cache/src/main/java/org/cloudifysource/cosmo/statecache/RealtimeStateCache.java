package org.cloudifysource.cosmo.statecache;

import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;

import java.net.URI;

/**
 * Holds a cache of the distributed system state. The state
 * is updated in real-time by listening to {@link org.cloudifysource.cosmo.statecache.messages.StateChangedMessage}s
 *
 * @author itaif
 * @since 0.1
 */
public class RealTimeStateCache {

    private final MessageConsumer consumer;
    private final URI messageTopic;
    private final StateCache stateCache;

    public RealTimeStateCache(RealTimeStateCacheConfiguration config) {

        this.consumer = new MessageConsumer();
        this.messageTopic = config.getMessageTopic();
        this.stateCache = new StateCache.Builder().build();
    }

    public void start() {
        this.consumer.addListener(messageTopic,
            new MessageConsumerListener() {
                @Override
                public void onMessage(URI uri, Object message) {
                    if (message instanceof StateChangedMessage) {
                        StateChangedMessage update = (StateChangedMessage)message;
                        stateCache.put(update.getResourceId(), update);
                    }
                    else {
                        throw new IllegalArgumentException("Cannot handle message " + message);
                    }
                }

                @Override
                public void onFailure(Throwable t) {
                    RealTimeStateCache.this.messageConsumerFailure(t);
                }

                @Override
                public Class getMessageClass() {
                    return Object.class;
                }
            });
    }

    public void stop() {
        this.consumer.removeAllListeners();
    }

    private void messageConsumerFailure(Throwable t) {
        //TODO: Logging framework
        System.err.println(t);
    }
}
