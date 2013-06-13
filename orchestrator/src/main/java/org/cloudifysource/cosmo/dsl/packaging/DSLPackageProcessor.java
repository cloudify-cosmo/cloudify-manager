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

package org.cloudifysource.cosmo.dsl.packaging;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.Charset;
import java.nio.file.DirectoryStream;
import java.nio.file.FileSystem;
import java.nio.file.FileSystems;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Used for processing cosmo DSL zip package files.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLPackageProcessor {

    /**
     * Processes a package file and returns the main DSL file and the root folder where the package was extracted to
     * as a {@link URI}.
     * @param packageFile The package file to process.
     * @param workDirectory The directory where the package will be extracted to.
     * @return DSL and package root directory.
     */
    public static ExtractedDSLPackageDetails process(File packageFile, File workDirectory) {
        Preconditions.checkArgument(packageFile.exists());
        unzip(packageFile, workDirectory);
        try {
            final Path dslPath = getDSLMainFile(workDirectory);
            final String dsl = com.google.common.io.Files.toString(dslPath.toFile(), Charset.defaultCharset());
            return new ExtractedDSLPackageDetails(dsl, workDirectory.toURI());
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    private static List<Path> getFiles(Path path, String pattern, boolean recursive) {
        if (Files.notExists(path)) {
            return Collections.emptyList();
        }
        final List<Path> files = Lists.newLinkedList();
        getFilesImpl(path, pattern, files, recursive);
        return files;
    }

    private static void getFilesImpl(Path path, String pattern, List<Path> files, boolean recursive) {
        try (DirectoryStream<Path> directoryStream = Files.newDirectoryStream(path, pattern)) {
            for (Path found : directoryStream) {
                files.add(found);
            }
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
        if (recursive) {
            try (DirectoryStream<Path> directoryStream = Files.newDirectoryStream(path)) {
                for (Path found : directoryStream) {
                    if (Files.isDirectory(found)) {
                        getFilesImpl(found, pattern, files, recursive);
                    }
                }
            } catch (IOException e) {
                throw Throwables.propagate(e);
            }
        }
    }


    private static Path getDSLMainFile(File workDirectory) {
        final List<Path> yamlFiles = getFiles(workDirectory.toPath(), "*.yaml", false);
        Preconditions.checkArgument(yamlFiles.size() > 0,
                "No yaml file found in package root");
        Preconditions.checkArgument(
                yamlFiles.size() == 1,
                "There is more than one yaml file in package root: %s",
                yamlFiles);
        return yamlFiles.get(0);
    }

    private static void unzip(File packageFile, final File workDirectory) {
        try {
            final Map<String, Object> env = Maps.newHashMap();
            env.put("create", "false");
            final URI uri = URI.create("jar:file:" + packageFile.getCanonicalPath());
            try (FileSystem zipfs = FileSystems.newFileSystem(uri, env)) {
                final Path path = zipfs.getPath("/");
                Files.walkFileTree(path, new SimpleFileVisitor<Path>() {
                    @Override
                    public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                        final Path target = Paths.get(workDirectory.getCanonicalPath(), file.toString());
                        Files.copy(file, target, StandardCopyOption.REPLACE_EXISTING);
                        return FileVisitResult.CONTINUE;
                    }
                    @Override
                    public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                        final Path directory = Paths.get(workDirectory.getCanonicalPath(), dir.toString());
                        if (Files.notExists(directory)) {
                            Files.createDirectory(directory);
                        }
                        return FileVisitResult.CONTINUE;
                    }
                });
            }
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

}
