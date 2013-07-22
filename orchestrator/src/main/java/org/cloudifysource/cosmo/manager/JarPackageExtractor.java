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

package org.cloudifysource.cosmo.manager;

import com.google.common.base.Preconditions;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.nio.file.FileSystem;
import java.nio.file.FileSystemNotFoundException;
import java.nio.file.FileSystems;
import java.nio.file.FileVisitResult;
import java.nio.file.FileVisitor;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.HashMap;

/**
 * Utility methods to extract files based on their package from JAR files.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class JarPackageExtractor {

    private static final Logger LOG = LoggerFactory.getLogger(JarPackageExtractor.class);

    /**
     * Extracts `absolutePackagePath` to `target`. This method assumes the JAR containing the package
     * is the same JAR this class belongs to
     * @param absolutePackagePath The package to extract.
     * @param target The target to extract files to.
     */
    public static void extractPackage(String absolutePackagePath, final Path target) throws IOException {
        String rawResource = JarPackageExtractor.class.getName().replace('.', '/') + ".class";
        URL resource = Resources.getResource(rawResource);
        extractPackage(absolutePackagePath, target, resource);
    }

    /**
     * Extracts `absolutePackagePath` to `target` using `containedResource` as means of locating the JAR file to
     * extract from.
     * @param absolutePackagePath The package to extract.
     * @param target The target to extract files to.
     * @param containedResource A {@link URL} pointing to a resource that is inside a jar file. It is used
     *                          to extract the JAR from which the extraction should be made.
     */
    public static void extractPackage(String absolutePackagePath, final Path target,
                                      URL containedResource) throws IOException {
        LOG.debug("Extracting package [{}] to [{}]. Using resource [{}] to locate a suitable jar file",
                absolutePackagePath, target, containedResource);

        // validations and setup
        Preconditions.checkNotNull(absolutePackagePath, "absolutePackagePath");
        Preconditions.checkNotNull(containedResource, "containedResource");
        Preconditions.checkNotNull(target, "target");

        if (!absolutePackagePath.startsWith("/")) {
            absolutePackagePath = "/" + absolutePackagePath;
        }

        FileVisitor<Path> visitor = new SimpleFileVisitor<Path>() {

            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                Files.createDirectories(resolveTarget(dir));
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                Files.copy(file, resolveTarget(file), StandardCopyOption.REPLACE_EXISTING);
                return FileVisitResult.CONTINUE;
            }

            private Path resolveTarget(Path path) {
                if (path.toString().contains("classes")) {
                    return target.resolve(path.toString().split("classes")[1].substring(1));
                }
                return target.resolve(path.toString().substring(1));
            }
        };

        Path source = createSourcePath(absolutePackagePath, containedResource);

        Files.walkFileTree(source, visitor);
    }

    private static Path createSourcePath(String absolutePackagePath, URL containedResource) throws IOException {


        String protocol = containedResource.getProtocol();

        switch (protocol) {

            case "jar":
                Preconditions.checkArgument(protocol.equals("jar"),
                        "resource must be contained in a jar file [%s]", containedResource);
                String[] splitContainedResource = containedResource.toString().split("!");
                Preconditions.checkArgument(splitContainedResource.length == 2,
                        "Invalid contained resource %s for package %s",
                        containedResource.toString(), absolutePackagePath);

                URI jarPath = URI.create(splitContainedResource[0]);
                FileSystem fileSystem;

                try {
                    fileSystem = FileSystems.getFileSystem(jarPath);
                } catch (FileSystemNotFoundException e) {
                    fileSystem = FileSystems.newFileSystem(jarPath, new HashMap<String,
                            Object>());
                }

                return fileSystem.getPath(absolutePackagePath);


            case "file":
                String dirPath = (containedResource.toString().split("classes")[0] + "classes").split("file:")[1];
                return Paths.get(dirPath, absolutePackagePath);
            default:
                throw new UnsupportedOperationException("Unsupported file protocol : " + protocol);
        }
    }
}
