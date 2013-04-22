package org.cloudifysource.cosmo.broker;

import com.google.common.base.Preconditions;
import org.atmosphere.annotation.Broadcast;
import org.atmosphere.annotation.Suspend;
import org.atmosphere.cpr.Broadcaster;
import org.atmosphere.jersey.Broadcastable;

import javax.ws.rs.FormParam;
import javax.ws.rs.GET;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;

@Path("/{topic}")
public class RestBrokerServlet {

    @PathParam("topic")
    private Broadcaster topic;

    @GET
    @Suspend(resumeOnBroadcast = true, listeners = {RestBrokerListener.class})
    public Broadcastable subscribe() {
        return new Broadcastable(topic);
    }

    @POST
    @Broadcast()
    public Broadcastable publish(String message) {
        Preconditions.checkNotNull(message);
        return new Broadcastable(message, topic);
    }
}