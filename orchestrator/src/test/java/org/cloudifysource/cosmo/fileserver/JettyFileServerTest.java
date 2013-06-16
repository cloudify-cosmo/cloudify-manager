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

import com.google.common.io.Resources;
import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.ListenableFuture;
import com.ning.http.client.Response;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.io.File;
import java.net.URL;

/**
 * Test for the {@link JettyFileServer} .
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */

public class JettyFileServerTest {

    @Test
    public void testStartFileServerAndDownloadFile() throws Exception {
        final URL resource = Resources.getResource("org/cloudifysource/cosmo/fileserver/test.txt");
        final String resourcePath = new File(resource.getPath()).getParentFile().getAbsolutePath();

        JettyFileServer server = new JettyFileServer(53229, resourcePath);
        try {
            AsyncHttpClient client = new AsyncHttpClient();
            final ListenableFuture<Response> listenableFuture =
                    client.prepareGet(new URL("http://localhost:53229/test.txt").toURI().toString()).execute();

            final Response response = listenableFuture.get();
            String responseBody = response.getResponseBody();

            Assert.assertEquals("test text file content", responseBody);
        } finally {
            server.close();
        }
    }

}
