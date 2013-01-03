package restlist.test;

import java.net.URI;
import java.net.URISyntaxException;

import javax.servlet.Servlet;

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

import restlist.server.RestListServlet;

import com.sun.jersey.spi.container.servlet.ServletContainer;

public class RestListTest {

	private static Server server;
	private static RestlistClient client;
	private static String restUri;
	
	private static ServletContainer servletContainer;

	@Parameters({"port"})
	@BeforeClass
	public static void startWebapp(
		@Optional("8081") int port) throws Exception {
	
	  restUri = "http://localhost:"+port+"/rest/";
	  client = new RestlistClient(new URI(restUri));
	  
	  server = new Server(port);
      servletContainer = new ServletContainer();
	  server.setHandler(createWebAppContext(servletContainer));
	  server.start();
	}

	@BeforeMethod
	public void restartServlet() {
		servletContainer.reload();
	}
	
	private static ServletContextHandler createWebAppContext(Servlet servlet) {
		ServletContextHandler handler = new ServletContextHandler(ServletContextHandler.SESSIONS);
        handler.setContextPath("/");
		ServletHolder servletHolder = new ServletHolder(servlet);
		servletHolder.setInitParameter("com.sun.jersey.config.property.packages", RestListServlet.class.getPackage().getName());
		handler.addServlet(servletHolder, "/rest/*");
		return handler;
	}

	@AfterClass
	public static void stopWebapp() throws Exception {
	  server.stop();
	}
	
	@Test
	public void hello() {
		client.put("test","1");
		String response = client.get("test");
		Assert.assertNotNull(response);
		Assert.assertEquals(response,"1");
	}
	
	@Test
	public void helloNotFound() throws URISyntaxException {
		String response = client.get("test");
		Assert.assertNull(response);
	}
}