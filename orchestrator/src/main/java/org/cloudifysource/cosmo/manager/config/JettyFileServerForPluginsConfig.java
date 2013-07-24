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

package org.cloudifysource.cosmo.manager.config;

import com.google.common.base.Throwables;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.fileserver.config.JettyFileServerConfig;
import org.cloudifysource.cosmo.manager.DSLPackage;
import org.cloudifysource.cosmo.manager.ResourceExtractor;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;

import javax.annotation.PostConstruct;
import javax.inject.Inject;
import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;

/**
 * Creates a new {@link JettyFileServerConfig}.
 *
 * Sets the resourceBase of the file server to a temporary directory created by {@link TemporaryDirectoryConfig}
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@Configuration
@Import({
        TemporaryDirectoryConfig.class,
})
@PropertySource("org/cloudifysource/cosmo/manager/fileserver/jetty.properties")
public class JettyFileServerForPluginsConfig extends JettyFileServerConfig {

    private static final String TEMP = System.getProperty("java.io.tmpdir") + "/cosmo";

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    private final Path pluginExtractionPath;

    public JettyFileServerForPluginsConfig() {
        pluginExtractionPath = Paths.get(TEMP + "/plugins");
    }

    @PostConstruct
    public void setResourceBase() {
        // zip webserver plugin
        createZipForPlugin(
                "celery/app/cosmo/cloudify/tosca/artifacts/plugin/python_webserver/installer",
                temporaryDirectory.get(),
                "python-webserver-installer.zip");
        this.resourceBase = temporaryDirectory.get().getAbsolutePath();
    }

    private void createZipForPlugin(final String resourceRoot,
                                           File targetDir, String targetName) {

        try {
            final DSLPackage.DSLPackageBuilder packagedPluginBuilder = new DSLPackage.DSLPackageBuilder();
            URL visitorRootUrl = Resources.getResource(resourceRoot);

            ResourceExtractor.extractResource(resourceRoot, pluginExtractionPath, visitorRootUrl);
            Files.walkFileTree(pluginExtractionPath.resolve(resourceRoot), new SimpleFileVisitor<Path>() {
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    if (file.toString().endsWith(".pyc")) {
                        return FileVisitResult.CONTINUE;
                    }
                    byte[] content = com.google.common.io.Files.toByteArray(file.toFile());
                    String targetFile = pluginExtractionPath.resolve(resourceRoot).relativize(file).toString();
                    packagedPluginBuilder.addFile(targetFile, content);
                    return FileVisitResult.CONTINUE;
                }
            });
            packagedPluginBuilder.build().write(new File(targetDir, targetName));
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }
}
