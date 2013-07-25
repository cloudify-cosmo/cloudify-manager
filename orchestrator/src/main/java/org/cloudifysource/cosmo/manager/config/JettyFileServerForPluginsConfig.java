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

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.fileserver.config.JettyFileServerConfig;
import org.cloudifysource.cosmo.utils.Archive;
import org.cloudifysource.cosmo.utils.ResourceExtractor;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

import javax.annotation.PostConstruct;
import javax.inject.Inject;
import java.io.File;
import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
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
@PropertySource("org/cloudifysource/cosmo/manager/fileserver/jetty.properties")
public class JettyFileServerForPluginsConfig extends JettyFileServerConfig {

    private static final String PLUGIN_RESOURCE_PATH =
            "celery/app/cosmo/cloudify/tosca/artifacts/plugin/python_webserver/installer";

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @PostConstruct
    public void setResourceBase() throws IOException {

        // create a directory for the file server inside the temp folder.
        File resourceBase = new File(temporaryDirectory.get().getAbsolutePath() + "/fileserver");
        Preconditions.checkArgument(resourceBase.mkdirs());

        // extract the plugin to the temp folder
        ResourceExtractor.extractResource(PLUGIN_RESOURCE_PATH, temporaryDirectory.get().toPath());

        // zip up the plugin and move the zip file to the file server resource base.
        createZipForPlugin(PLUGIN_RESOURCE_PATH,
                           resourceBase,
                           "python-webserver-installer.zip");
        this.resourceBase = resourceBase.getAbsolutePath();
    }

    private void createZipForPlugin(final String resourceRoot,
                                           File targetDir, String targetName) {

        try {
            final Archive.ArchiveBuilder packagedPluginBuilder = new Archive.ArchiveBuilder();
            Files.walkFileTree(temporaryDirectory.get().toPath().resolve(resourceRoot), new SimpleFileVisitor<Path>() {
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    if (file.toString().endsWith(".pyc")) {
                        return FileVisitResult.CONTINUE;
                    }
                    byte[] content = com.google.common.io.Files.toByteArray(file.toFile());
                    String targetFile = temporaryDirectory.get().toPath()
                            .resolve(resourceRoot).relativize(file).toString();
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
