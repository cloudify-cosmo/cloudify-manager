package org.openspaces.servicegrid.kvstore;

import javax.ws.rs.core.EntityTag;

import org.testng.Assert;
import org.testng.annotations.AfterClass;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import com.sun.jersey.api.client.Client;
import com.sun.jersey.api.client.ClientResponse;
import com.sun.jersey.api.client.UniformInterfaceException;
import com.sun.jersey.api.client.WebResource;
import com.sun.jersey.api.client.config.ClientConfig;
import com.sun.jersey.api.client.config.DefaultClientConfig;

public class KVStoreTest {

	private static String restUri;
	private static WebResource webResource;
	private static KVStoreServer server;
	
	@Parameters({"port"})
	@BeforeClass
	public static void startWebapp(
		@Optional("8081") int port) throws Exception {
	
	  restUri = "http://localhost:"+port+"/";
	  final ClientConfig clientConfig = new DefaultClientConfig();
	  final Client client = Client.create(clientConfig);
	  webResource = client.resource(restUri);
	  
	  server = new KVStoreServer();
	  server.start(port);
	}

	@BeforeMethod
	public void restartServlet() {
		server.reload();
	}

	@AfterClass
	public static void stopWebapp() throws Exception {
	  server.stop();
	}
	
	@Test
	public void hello() {
		webResource.path("test").put("1");
		String response = webResource.path("test").get(String.class);
		Assert.assertNotNull(response);
		Assert.assertEquals(response,"1");
	}
	
	@Test
	public void helloNotFound() {
		try {
			webResource.path("test").get(String.class);
			Assert.fail("Expected exception");
		}
		catch (UniformInterfaceException e) {
			Assert.assertEquals(e.getResponse().getStatus(),ClientResponse.Status.NOT_FOUND.getStatusCode());
		}
	}
	
	@Test
	public void helloEtag() {
		ClientResponse putResponse = webResource.path("test").header("If-None-Match", "*").put(ClientResponse.class, "1");
		ClientResponse getResponse = webResource.path("test").get(ClientResponse.class);
		EntityTag etag = getResponse.getEntityTag();
		Assert.assertEquals(getResponse.getEntity(String.class), "1");
		Assert.assertEquals(etag, putResponse.getEntityTag());
		webResource.path("test").header("If-Match", etag).put("2");
		Assert.assertEquals(webResource.path("test").get(String.class),"2");
	}
	
	@Test
	public void helloWrongIfMatchEtag() {
		webResource.path("test").header("If-None-Match", "*").put("1");
		ClientResponse getResponse = webResource.path("test").get(ClientResponse.class);
		Assert.assertEquals(getResponse.getEntity(String.class), "1");    		
		final EntityTag wrongEtag = KVEntityTag.create("0");
		ClientResponse putResponse = webResource.path("test").header("If-Match", wrongEtag).put(ClientResponse.class, "2");
		Assert.assertEquals(putResponse.getStatus(),ClientResponse.Status.PRECONDITION_FAILED.getStatusCode());
		Assert.assertEquals(putResponse.getEntityTag(), getResponse.getEntityTag());
	}
	
	@Test
	public void helloWrongIfNoneMatchEtag() {
		ClientResponse putResponse1 = webResource.path("test").header("If-None-Match", "*").put(ClientResponse.class, "1");
		Assert.assertEquals(putResponse1.getStatus(),ClientResponse.Status.OK.getStatusCode());
		ClientResponse putResponse2 =webResource.path("test").header("If-None-Match", "*").put(ClientResponse.class, "2");
		Assert.assertEquals(putResponse2.getStatus(),ClientResponse.Status.PRECONDITION_FAILED.getStatusCode());
		Assert.assertEquals(putResponse1.getEntityTag(), putResponse2.getEntityTag());
	}
	
	@Test
	public void helloWrongIfMatchEtagWhenEmpty() {
		final EntityTag wrongEtag = KVEntityTag.create("0");
		ClientResponse putResponse = webResource.path("test").header("If-Match", wrongEtag).put(ClientResponse.class, "1");
		Assert.assertEquals(putResponse.getStatus(),ClientResponse.Status.PRECONDITION_FAILED.getStatusCode());
		Assert.assertEquals(putResponse.getEntityTag(), null);
	}
	
	@Test
	public void helloWrongKey() {
		try {
			webResource.path("test/_list").put("1");
		}
		catch (UniformInterfaceException e) {
			Assert.assertEquals(e.getResponse().getStatus(),ClientResponse.Status.BAD_REQUEST.getStatusCode());
		}
	}
	
	@Test
	public void list() {
		webResource.path("test/1").put("1");
		webResource.path("test/2").put("2");
		String response = webResource.path("test/_list").get(String.class);
		String trimmed = response.replaceAll("(\\r|\\n|\\s)", "");
		Assert.assertEquals(trimmed, "[\""+restUri+"test/1\",\""+restUri+"test/2\"]");
	}
}