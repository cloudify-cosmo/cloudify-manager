/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *******************************************************************************/
package org.cloudifysource.cosmo.messaging.broker;

import org.atmosphere.container.Jetty7CometSupport;
import org.atmosphere.cpr.ApplicationConfig;
import org.atmosphere.cpr.AtmosphereServlet;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;

import com.google.common.base.Throwables;

import java.net.URI;

/**
 * Starts a jetty server, with jersey servlet container running the {@link MessageBrokerServlet}.
 * @author Itai Frenkel
 * @since 0.1
 */
public class MessageBrokerServer {
    private static Server server;
    private static AtmosphereServlet atmoServlet;
    private URI uri;
    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    public void start(int port) {
        this.uri = URI.create("http://localhost:" + port + "/");
        server = new Server(port);
        server.setHandler(createWebAppContext(MessageBrokerServlet.class));
        try {
            server.start();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public void stop() {
        this.uri = null;
        atmoServlet.destroy();

        try {
            server.stop();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    private static ServletContextHandler createWebAppContext(Class servletClass) {

        atmoServlet = new AtmosphereServlet();

        final ServletContextHandler context = new ServletContextHandler(ServletContextHandler.SESSIONS);
        context.setContextPath("/");
        context.addServlet(atmosphereServletHolder(servletClass), "/*");
        return context;
    }

    private static ServletHolder atmosphereServletHolder(Class servletClass) {
        ServletHolder holder = new ServletHolder(AtmosphereServlet.class);
        holder.setInitParameter(
                "com.sun.jersey.config.property.packages",
                servletClass.getPackage().getName());
        //https://github.com/Atmosphere/atmosphere/wiki/ClassNotFoundException-at-startup
        //@see: org.atmosphere.cpr.DefaultAsyncSupportResolver
        holder.setInitParameter(
                ApplicationConfig.PROPERTY_COMET_SUPPORT,
                Jetty7CometSupport.class.getName());

        return holder;
    }

    public URI getUri() {
        return uri;
    }
}
