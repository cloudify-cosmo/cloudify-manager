package org.openspaces.servicegrid.kvstore;

import java.net.URI;
import java.net.URISyntaxException;

import javax.ws.rs.GET;
import javax.ws.rs.PUT;
import javax.ws.rs.Path;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.EntityTag;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Request;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.Response.ResponseBuilder;
import javax.ws.rs.core.Response.Status;
import javax.ws.rs.core.UriInfo;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.sun.jersey.api.Responses;
import com.sun.jersey.spi.resource.Singleton;

@Path("/")
@Singleton
public class KVStoreServlet {
 
	private static final String LIST_ALL_POSTFIX = "/*/_list";

	@GET
	@Path("{any:.*}")
	public Response get(@Context UriInfo uriInfo, @Context Request request) {
		final URI key =  uriInfo.getAbsolutePath();
		String keyString = key.toString();
		if (keyString.endsWith(LIST_ALL_POSTFIX)) {
			return list(newURI(keyString.substring(0, keyString.length()-LIST_ALL_POSTFIX.length()+1)), request);
		}
		return get(key);
	}

	private Response get(final URI key) {
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
	
	 private Response list(URI keyPrefix, Request request) {
		
		 final Iterable<URI> list = KVStoreHolder.getStore().listKeysStartsWith(keyPrefix);
		 return Response.ok().type(MediaType.APPLICATION_JSON_TYPE).entity(Iterables.toString(list)).build();
	}

	private URI newURI(String uri) {
		try {
			return new URI(uri);
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	@PUT
	 @Path("{any:.*}")
	 public Response putContainer(String state, @Context UriInfo uriInfo, @Context Request request) {
	     
	    final URI key =  uriInfo.getAbsolutePath();
	    if (key.toString().endsWith(LIST_ALL_POSTFIX)) {
	    	return Response.status(Status.BAD_REQUEST).entity("{\"error\":\"URI must not end with" + LIST_ALL_POSTFIX +"\"}").build();
	    }
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
