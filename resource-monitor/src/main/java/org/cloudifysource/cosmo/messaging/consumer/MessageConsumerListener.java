package org.cloudifysource.cosmo.messaging.consumer;

import java.net.URI;

/**
 * Created with IntelliJ IDEA.
 * User: itaif
 * Date: 23/04/13
 * Time: 09:52
 * To change this template use File | Settings | File Templates.
 */
public interface MessageConsumerListener {

    void onMessage(URI uri, String message);

    void onFailure(Throwable t);
}
