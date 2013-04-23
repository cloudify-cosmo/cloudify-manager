package org.cloudifysource.cosmo.messaging.producer;

import com.google.common.base.Throwables;
import com.google.common.util.concurrent.ListenableFuture;
import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.Response;

import java.io.IOException;
import java.net.URI;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Client for sending messages to the message broker.
 */
public class MessageProducer {

    AsyncHttpClient client;

    public MessageProducer() {
            client = new AsyncHttpClient();
    }

    public ListenableFuture send(URI uri, String message) {
        try {
            return convertListenableFuture(
                    client.preparePost(uri.toString())
                    .setBody(message)
                    .execute());
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private ListenableFuture convertListenableFuture(final com.ning.http.client.ListenableFuture<Response> future) {
        return new ListenableFuture() {
            @Override
            public void addListener(Runnable listener, Executor executor) {
                future.addListener(listener, executor);
            }

            @Override
            public boolean cancel(boolean mayInterruptIfRunning) {
                return future.cancel(mayInterruptIfRunning);
            }

            @Override
            public boolean isCancelled() {
                return future.isCancelled();
            }

            @Override
            public boolean isDone() {
                return future.isDone();
            }

            @Override
            public Object get() throws InterruptedException, ExecutionException {
                return future.get();
            }

            @Override
            public Object get(long timeout, TimeUnit unit)
                    throws InterruptedException, ExecutionException, TimeoutException {
                return future.get(timeout, unit);
            }
        };
    }
}
