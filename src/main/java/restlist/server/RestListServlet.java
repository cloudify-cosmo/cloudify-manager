package restlist.server;

import java.net.URI;
import java.util.HashMap;
import java.util.Map;

import javax.ws.rs.GET;
import javax.ws.rs.PUT;
import javax.ws.rs.Path;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.Request;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.UriInfo;

import com.sun.jersey.api.Responses;
import com.sun.jersey.spi.resource.Singleton;

@Path("/")
@Singleton
public class RestListServlet {
 
	private Map<URI, String> data = new HashMap<URI, String>();
	
	@GET
	@Path("/{any}")
	public Response get(@Context UriInfo uriInfo, @Context Request request) {
		URI uri =  uriInfo.getAbsolutePath();
		String response = data.get(uri);
		if (response == null) {
			return Response.status(Responses.NOT_FOUND).build();
		}
		return Response.ok().entity(response).build();
	}
	
	 @PUT
	 @Path("/{any}")
	 public Response putContainer(String message,@Context UriInfo uriInfo, @Context Request request) {
	     
	     URI uri =  uriInfo.getAbsolutePath();
	 
	     Response r;
	     String existing = data.get(uri);
	     
	     if (existing == null) {
	         r = Response.created(uri).build();
	     } 
	     else if (existing.equals(message)){
	         r = Response.notModified().build();
	     }
	     else {
	    	 r = Response.ok().build();
	     }
	     data.put(uri, message);
	     return r;
	 }
}
