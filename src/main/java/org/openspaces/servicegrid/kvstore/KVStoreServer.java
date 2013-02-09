package org.openspaces.servicegrid.kvstore;

import javax.servlet.Servlet;

import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;

import com.google.common.base.Throwables;
import com.sun.jersey.spi.container.servlet.ServletContainer;

public class KVStoreServer {

	private static Server server;
	private static ServletContainer servletContainer;
	
	public void start(int port) {

		server = new Server(port);
	    servletContainer = new ServletContainer(new KVStoreResourceConfig());
		server.setHandler(createWebAppContext(servletContainer));
		try {
			server.start();
		}
		catch (Exception e) {
			throw Throwables.propagate(e);
		}
	}
	
	public void reload() {
		servletContainer.reload();
	}
	
	public void stop() {
		try {
			server.stop();
		}
		catch (Exception e) {
			throw Throwables.propagate(e);
		}
	}
	
	private static ServletContextHandler createWebAppContext(Servlet servlet) {
		ServletContextHandler handler = new ServletContextHandler(ServletContextHandler.SESSIONS);
		handler.setContextPath("/");
		ServletHolder servletHolder = new ServletHolder(servlet);
		servletHolder.setInitParameter("com.sun.jersey.config.property.packages", KVStoreServlet.class.getPackage().getName());
		handler.addServlet(servletHolder, "/*");
		return handler;
	}
}
