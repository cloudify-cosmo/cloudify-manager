package restlist.test;


import java.net.URI;

import com.sun.jersey.api.client.Client;
import com.sun.jersey.api.client.ClientResponse;
import com.sun.jersey.api.client.UniformInterfaceException;
import com.sun.jersey.api.client.WebResource;
import com.sun.jersey.api.client.config.ClientConfig;
import com.sun.jersey.api.client.config.DefaultClientConfig;

public class RestlistClient {
	
	private final Client client;
	private final WebResource webResource;
	
	public RestlistClient(URI restUri) {
		ClientConfig clientConfig = new DefaultClientConfig();
		client = Client.create(clientConfig);
		webResource = client.resource(restUri);
	}
	
	/**
	 * @return the value in the specified path, or null if not exists
	 */
	public String get(String path) {
		try { 
			return 
				webResource
				.path(path)
				.get(String.class);
		}
		catch (UniformInterfaceException e) {
			if (e.getResponse().getStatus() == ClientResponse.Status.NOT_FOUND.getStatusCode()) {
				return null;
			}
			throw e;
		}
	}

	public void put(String path, String request) {
		webResource
		.path(path)
		.put(request);
	}
}
