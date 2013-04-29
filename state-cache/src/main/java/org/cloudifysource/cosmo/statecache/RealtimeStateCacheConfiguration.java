package org.cloudifysource.cosmo.statecache;

import java.net.URI;

/**
 * Configures {@link RealtimeStateCache} object.
 *
 * @author itaif
 * @since 0.1
 */
public class RealTimeStateCacheConfiguration {

    URI messageTopic;

    public URI getMessageTopic() {
        return messageTopic;
    }

    public void setMessageTopic(URI messageTopic) {
        this.messageTopic = messageTopic;
    }
}
