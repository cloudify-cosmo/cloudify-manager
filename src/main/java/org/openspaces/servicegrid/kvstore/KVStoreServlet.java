package org.openspaces.servicegrid.kvstore;

import java.net.URI;

import javax.ws.rs.GET;
import javax.ws.rs.PUT;
import javax.ws.rs.Path;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.EntityTag;
import javax.ws.rs.core.Request;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.Response.ResponseBuilder;
import javax.ws.rs.core.UriInfo;


import com.sun.jersey.api.Responses;
import com.sun.jersey.spi.resource.Singleton;

@Path("/")
@Singleton
public class KVStoreServlet {
 
	@GET
	@Path("/{any}")
	public Response get(@Context UriInfo uriInfo, @Context Request request) {
		final URI key =  uriInfo.getAbsolutePath();
		
		final EntityTag etag = KVStoreHolder.getStore().getEntityTag(key);
		
		if (etag.equals(KVEntityTag.EMPTY)) {
			return Response.status(Responses.NOT_FOUND).build();
		}
		
		final String state = KVStoreHolder.getStore().getState(key);
		
		return Response.ok()
			   .tag(etag)
			   .entity(state)
			   .build();
	}
	
	 @PUT
	 @Path("/{any}")
	 public Response putContainer(String state, @Context UriInfo uriInfo, @Context Request request) {
	     
	    final URI key =  uriInfo.getAbsolutePath();
	 
	    final EntityTag lastEtag = KVStoreHolder.getStore().getEntityTag(key);
		ResponseBuilder rb = request.evaluatePreconditions(lastEtag);
	     if (rb != null) {
	    	 return rb.build();
	     }
	     
	     EntityTag etag = KVStoreHolder.getStore().put(key, state);
	     
	    return Response.ok()
	    	   .tag(etag)
	    	   .build();
	 }
}
