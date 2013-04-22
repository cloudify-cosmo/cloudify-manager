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
package org.cloudifysource.cosmo.broker;

import org.atmosphere.container.Jetty7CometSupport;
import org.atmosphere.cpr.ApplicationConfig;
import org.atmosphere.cpr.AtmosphereServlet;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;

import com.google.common.base.Throwables;

/**
 * Starts a jetty server, with jersey servlet container running the {@link RestBrokerServlet}.
 * @author Itai Frenkel
 * @since 0.1
 */
public class RestBrokerServer {
    private static Server server;
    private static AtmosphereServlet atmoServlet;

    public void start(int port) {
        server = new Server(port);
        server.setHandler(createWebAppContext(RestBrokerServlet.class));
        try {
            server.start();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public void stop() {

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

        //holder.setInitParameter(
          //      ApplicationConfig.SERVLET_CLASS,
            //    servletClass.getName());
        holder.setInitParameter(
                "com.sun.jersey.config.property.packages",
                servletClass.getPackage().getName());
        //https://github.com/Atmosphere/atmosphere/wiki/ClassNotFoundException-at-startup
        //@see: JettyAsyncSupportWithWebSocket.class
        holder.setInitParameter(
                ApplicationConfig.PROPERTY_COMET_SUPPORT,
                Jetty7CometSupport.class.getName());

        return holder;
    }
}
