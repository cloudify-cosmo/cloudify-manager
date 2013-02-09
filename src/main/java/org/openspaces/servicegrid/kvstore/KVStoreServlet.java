package org.openspaces.servicegrid.kvstore;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Arrays;

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

import org.openspaces.servicegrid.kvstore.KVStore.EntityTagState;

import com.google.common.base.Function;
import com.google.common.base.Optional;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.sun.jersey.api.Responses;

@Path("/")
public class KVStoreServlet {
 
	private static final String LIST_ALL_POSTFIX = "/*/_list";

	@Context KVStore store;
	
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
		
		final Optional<EntityTagState<String>> value = store.getState(key);
		if (!value.isPresent()) {
			return Response.status(Responses.NOT_FOUND).build();
		}
		
		return Response.ok()
			   .tag(value.get().getEntityTag())
			   .entity(value.get().getState())
			   .build();
	}
	
	 private Response list(URI keyPrefix, Request request) {
		
		 final Iterable<URI> list = store.listKeysStartsWith(keyPrefix);
		 return Response.ok().type(MediaType.APPLICATION_JSON_TYPE).entity(toJson(list)).build();
	}

	private String toJson(Iterable<URI> uris) {
		return Arrays.toString(
			Iterables.toArray(Iterables.transform(uris, new Function<URI, String>() {
		
			@Override
			public String apply(URI input) {
				return "\"" + input +"\"";
			}
		}), String.class));
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
	 public Response put(String state, @Context UriInfo uriInfo, @Context Request request) {
	     
	    final URI key =  uriInfo.getAbsolutePath();
	    return put(state, key, request);
	 }

	private Response put(String state, final URI key, Request request) {
		if (key.toString().endsWith(LIST_ALL_POSTFIX)) {
	    	return Response.status(Status.BAD_REQUEST).entity("{\"error\":\"URI must not end with" + LIST_ALL_POSTFIX +"\"}").build();
	    }
	    
		Response r = evaluatePreconditions(key, request);
		if (r != null) {
			return r;
		}
	     
	     final EntityTag etag = store.put(key, state);
	     
	    return Response.ok()
	    	   .tag(etag)
	    	   .build();
	}

	private Response evaluatePreconditions(final URI key, Request request) {
		final Optional<EntityTag> lastEtag = store.getEntityTag(key);
	    ResponseBuilder rb;
	    if (!lastEtag.isPresent()) {
			rb = request.evaluatePreconditions();
		}
		else {
			final EntityTag eTag = lastEtag.get();
			rb = request.evaluatePreconditions(eTag);
			if (rb != null) {
				rb.tag(eTag);
			}
		}
	     if (rb != null) {
	    	 return rb.build();
	     }
	     return null;
	}
}
