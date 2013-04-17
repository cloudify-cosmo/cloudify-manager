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

package org.cloudifysource.cosmo.resource.mock;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Throwables;
import com.sun.jersey.api.core.PackagesResourceConfig;
import com.sun.jersey.core.spi.component.ComponentContext;
import com.sun.jersey.core.spi.component.ComponentScope;
import com.sun.jersey.spi.container.servlet.ServletContainer;
import com.sun.jersey.spi.inject.Injectable;
import com.sun.jersey.spi.inject.InjectableProvider;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;

import javax.servlet.Servlet;
import javax.ws.rs.core.Context;
import java.lang.reflect.Type;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Starts a jetty server, with jersey servlet container running the {@link org.cloudifysource.cosmo.resource.mock
 * .ResourceProvisionerServlet}.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ResourceProvisioningServerMock implements ResourceProvisioningServerListener {

    private static Server server;
    private static ServletContainer servletContainer;

    private AtomicInteger requestsCount = new AtomicInteger(0);
    private ResourceProvisioningServerListener listener;

    public void start(int port) {
        server = new Server(port);
        Map<String, Object> props = Maps.newHashMap();
        props.put("com.sun.jersey.config.property.packages",
                ResourceProvisioningServletMock.class.getPackage().getName());
        servletContainer = new ServletContainer(new ResourceProvisioningResourceConfig(this, props));
        server.setHandler(createWebAppContext(servletContainer));
        try {
            server.start();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public void reload() {
        servletContainer.reload();
    }

    public void stop() {
        try {
            server.stop();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    private static ServletContextHandler createWebAppContext(Servlet servlet) {
        ServletContextHandler handler = new ServletContextHandler(ServletContextHandler.SESSIONS);
        handler.setContextPath("/");
        ServletHolder servletHolder = new ServletHolder(servlet);
        servletHolder.setInitParameter(
                "com.sun.jersey.config.property.packages",
                ResourceProvisioningServletMock.class.getPackage().getName());
        servletHolder.setInitParameter("cacheControl", "max-age=0,public");
        handler.addServlet(servletHolder, "/*");
        return handler;
    }

    public void setListener(ResourceProvisioningServerListener listener) {
        this.listener = listener;
    }

    @Override
    public void onRequest() {
        requestsCount.incrementAndGet();
        if (listener != null)
            listener.onRequest();
    }

    public int getRequestsCount() {
        return requestsCount.get();
    }

    /**
     * Resource config for {@link ResourceProvisioningServerMock}.
     */
    private class ResourceProvisioningResourceConfig extends PackagesResourceConfig {
        public ResourceProvisioningResourceConfig(ResourceProvisioningServerListener listener,
                                                  Map<String, Object> props) {
            super(props);
            getSingletons().add(new ListenerProvider(listener));
        }
    }

    /**
     * {@link ResourceProvisioningServerListener} provider.
     */
    private class ListenerProvider
            implements InjectableProvider<Context, Type>, Injectable<ResourceProvisioningServerListener> {

        private final ResourceProvisioningServerListener listener;

        public ListenerProvider(ResourceProvisioningServerListener listener) {
            this.listener = listener;
        }

        @Override
        public ResourceProvisioningServerListener getValue() {
            return listener;
        }
        @Override
        public ComponentScope getScope() {
            return ComponentScope.Singleton;
        }
        @Override
        public Injectable<ResourceProvisioningServerListener> getInjectable(ComponentContext componentContext,
                                                                            Context context, Type type) {
            if (type.equals(ResourceProvisioningServerListener.class))
                return this;
            return null;
        }
    }

}

