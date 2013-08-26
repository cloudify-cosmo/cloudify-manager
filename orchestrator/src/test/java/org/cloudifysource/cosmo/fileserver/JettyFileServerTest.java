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

package org.cloudifysource.cosmo.fileserver;

import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.ListenableFuture;
import com.ning.http.client.Response;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.fileserver.config.JettyFileServerTestConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.Assert;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URL;

/**
 * Test for the {@link JettyFileServer} .
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */

@ContextConfiguration(classes = { JettyFileServerTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class JettyFileServerTest extends AbstractTestNGSpringContextTests {

    /**
     * Test configuration.
     */
    @Configuration
    @Import({
            JettyFileServerTestConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/fileserver/config/test.properties")
    static class Config extends TestConfig {
    }

    @Value("${cosmo.file-server.port}")
    private int port;

    @Value("${cosmo.file-server-test.test-file-name}")
    private String fileName;

    @Inject
    private JettyFileServer server;

    @Test
    public void testStartFileServerAndDownloadFile() throws Exception {
        AsyncHttpClient client = new AsyncHttpClient();
        final ListenableFuture<Response> listenableFuture =
                client.prepareGet(new URL("http://localhost:" + port + "/" + fileName).toURI().toString()).execute();

        final Response response = listenableFuture.get();
        String responseBody = response.getResponseBody();

        Assert.assertEquals("test text file content", responseBody);

    }

}
