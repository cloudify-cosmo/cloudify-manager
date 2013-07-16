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
 ******************************************************************************/

package org.cloudifysource.cosmo.orchestrator.integration.config;

import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.orchestrator.integration.monitor.MockPortKnocker;
import org.cloudifysource.cosmo.orchestrator.integration.monitor.PortKnockingDescriptor;
import org.robotninjas.riemann.client.RiemannTcpClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.inject.Inject;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.UnknownHostException;
import java.util.List;

/**
 * Creates a new {@link MockPortKnocker}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class MockPortKnockerConfig {

    // format is string delimited list of
    // {host}:{port}:{resourceId}
    @Value("${cosmo.test.port-knocker.sockets-to-knock}")
    private String[] socketsToKnock;

    @Inject
    RiemannTcpClient riemannTcpClient;

    @Bean(destroyMethod = "close")
    public MockPortKnocker mockPortKnocker() throws UnknownHostException {

        List<PortKnockingDescriptor> descriptors = Lists.newArrayList();
        for (String socketToKnock : socketsToKnock) {
            String[] hostPortAndResourceId = socketToKnock.split(":");
            InetAddress address = InetAddress.getByName(hostPortAndResourceId[0]);
            int port = Integer.parseInt(hostPortAndResourceId[1]);
            String resourceId = hostPortAndResourceId[2];
            InetSocketAddress socketAddress = new InetSocketAddress(address, port);
            descriptors.add(new PortKnockingDescriptor(socketAddress, resourceId));
        }
        return new MockPortKnocker(
            riemannTcpClient,
            descriptors);
    }

}
