package org.openspaces.servicegrid.kvstore;

import javax.servlet.Servlet;
import javax.ws.rs.core.EntityTag;

import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;
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
import com.sun.jersey.spi.container.servlet.ServletContainer;

public class KVStoreTest {

	private static Server server;
	
	private static String restUri;
	
	private static ServletContainer servletContainer;
	
	private static WebResource webResource;
	
	@Parameters({"port"})
	@BeforeClass
	public static void startWebapp(
		@Optional("8081") int port) throws Exception {
	
	  restUri = "http://localhost:"+port+"/rest/";
	  final ClientConfig clientConfig = new DefaultClientConfig();
	  final Client client = Client.create(clientConfig);
	  webResource = client.resource(restUri);
	  
	  server = new Server(port);
      servletContainer = new ServletContainer();
	  server.setHandler(createWebAppContext(servletContainer));
	  server.start();
	}

	@BeforeMethod
	public void restartServlet() {
		servletContainer.reload();
		KVStoreHolder.clear();
	}
	
	private static ServletContextHandler createWebAppContext(Servlet servlet) {
		ServletContextHandler handler = new ServletContextHandler(ServletContextHandler.SESSIONS);
        handler.setContextPath("/");
		ServletHolder servletHolder = new ServletHolder(servlet);
		servletHolder.setInitParameter("com.sun.jersey.config.property.packages", KVStoreServlet.class.getPackage().getName());
		handler.addServlet(servletHolder, "/rest/*");
		return handler;
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
		webResource.path("test").put("1");
		ClientResponse response = webResource.path("test").get(ClientResponse.class);
		EntityTag etag = response.getEntityTag();
		Assert.assertEquals(response.getEntity(String.class), "1");
		webResource.path("test").header("If-Match", etag).put("2");
		Assert.assertEquals(webResource.path("test").get(String.class),"2");
	}
	
	@Test
	public void helloWrongEtag() {
		webResource.path("test").put("1");
		ClientResponse response = webResource.path("test").get(ClientResponse.class);
		Assert.assertEquals(response.getEntity(String.class), "1");
		    		
		try {
			final EntityTag wrongEtag = KVEntityTag.create("0");
			webResource.path("test").header("If-Match", wrongEtag).put("2");
			Assert.fail("Expected exception");
		}
		catch (UniformInterfaceException e) {
			Assert.assertEquals(e.getResponse().getStatus(),ClientResponse.Status.PRECONDITION_FAILED.getStatusCode());
		}
	}
}