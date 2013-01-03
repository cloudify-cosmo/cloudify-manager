package restlist.server;

import java.net.URI;
import java.util.List;

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
 
	@GET
	@Path("/{any}")
	public Response get(@Context UriInfo uriInfo, @Context Request request) {
		URI uri =  uriInfo.getAbsolutePath();
		List<String> entities = ListHolder.getData().get(uri);
		
		if (entities.isEmpty()) {
			return Response.status(Responses.NOT_FOUND).build();
		}
		String lastEntity = entities.get(entities.size()-1);
		return Response.ok().entity(lastEntity).build();
	}
	
	 @PUT
	 @Path("/{any}")
	 public Response putContainer(String newEntity, @Context UriInfo uriInfo, @Context Request request) {
	     
	     URI uri =  uriInfo.getAbsolutePath();
	 
	     Response r;
	     
	     if (!ListHolder.getData().containsKey(uri)) {
	         r = Response.created(uri).build();
	     } 
	     else {
	    	 r = Response.ok().build();
	     }
	     ListHolder.getData().put(uri, newEntity);
	     return r;
	 }
}
