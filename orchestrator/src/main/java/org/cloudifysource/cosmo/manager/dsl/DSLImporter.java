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

package org.cloudifysource.cosmo.manager.dsl;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.dsl.packaging.DSLPackageProcessor;
import org.cloudifysource.cosmo.utils.Archive;
import org.cloudifysource.cosmo.utils.ResourceExtractor;

import java.io.File;
import java.io.FilenameFilter;
import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;

/**
 * Imports the DSL directory into the target dir.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
public class DSLImporter {

    private String targetPath;
    private File temporaryDirectory;
    private String locatorPrefix;

    public DSLImporter(String targetPath,
                       File temporaryDirectory,
                       String locatorPrefix) {
        this.targetPath = targetPath;
        // create a directory for the file server inside the temp folder.
        File resourceBase = new File(targetPath);
        if (!resourceBase.isDirectory()) {
            Preconditions.checkArgument(resourceBase.mkdirs());
        }
        this.temporaryDirectory = temporaryDirectory;
        this.locatorPrefix = locatorPrefix;
    }


    public String importAliasMapping(Path aliasMappingPath) throws IOException {
        Path source = Paths.get(this.temporaryDirectory.toString(), aliasMappingPath.toString());
        Path newdir = Paths.get(this.targetPath);
        Files.copy(source, newdir.resolve(source.getFileName()), StandardCopyOption.REPLACE_EXISTING);
        return locatorPrefix + aliasMappingPath.toFile().getName();
    }

    /**
     * This method imports the dsl resource into the file server resource base.
     * It does 2 things:
     * 1. Copy the entire dsl resource to the file server resource base.
     * 2. Zip up the plugins and copy them to the filer server resource base.
     *
     * @param dslPath - Absolute path to the dsl resource. if you want to pass a dsl classpath resource locator use
     * {@link #importDSL(String)}
     * @return Location to the dsl file.
     */
    public String importDSL(Path dslPath) throws IOException {

        File dslFile = dslPath.toFile();
        if (dslFile.isDirectory()) {
            dslPath = DSLPackageProcessor.getDSLMainFile(dslFile);
        }
        return copyDSLFiles(dslPath);
    }

    /**
     * This method imports the dsl resource into the file server resource base.
     * It does 2 things:
     * 1. Copy the entire dsl resource to the file server resource base.
     * 2. Zip up the plugins and copy them to the filer server resource base.
     *
     * @param dslResourcePath - resource locator of the dsl package.
     * @return Location to the dsl file.
     * @throws IOException
     */
    public String importDSL(String dslResourcePath) throws IOException {

        int lastSeparator = dslResourcePath.lastIndexOf("/");
        String dslParent = dslResourcePath.substring(0, lastSeparator);

        ResourceExtractor
                .extractResource(dslParent, temporaryDirectory.toPath());
        Path path = Paths.get(temporaryDirectory.toString() + "/" + dslResourcePath);
        return copyDSLFiles(path);

    }

    private String copyDSLFiles(Path absolutePathToDSL) throws IOException {
        String parent = absolutePathToDSL.toFile().getParent();
        copyPlugins(Paths.get(parent + "/plugins"));
        copyDSL(Paths.get(parent));
        return locatorPrefix + absolutePathToDSL.toFile().getParentFile().getName() + "/" +
                absolutePathToDSL.toFile().getName();
    }

    public String importCosmoResources(Path resourcesPath) throws IOException {
        String source = this.temporaryDirectory.toString() + "/" + resourcesPath.toString();
        String target = targetPath + "/resources/" + resourcesPath.toString();
        File targetDir = new File(target);
        targetDir.mkdirs();
        copyDirectory(Paths.get(source), Paths.get(target));
        return locatorPrefix + "resources/";
    }

    private void copyPlugins(Path pluginsPath) throws IOException {

        File pluginsDirectory = pluginsPath.toFile();
        if (!pluginsDirectory.exists())
            return;
        String[] plugins = pluginsDirectory.list(new FilenameFilter() {

            @Override
            public boolean accept(File dir, String name) {
                return new File(dir, name).isDirectory();
            }
        });

        for (String pluginDir : plugins) {
            String finalZipName = pluginDir + ".zip";
            Path pluginResourcePath = Paths.get(pluginsPath.toString(), pluginDir);
            createZipForPlugin(pluginResourcePath.toString(), new File(targetPath), finalZipName);
        }
    }

    private void copyDSL(Path dslPath) throws IOException {
        copyDirectory(dslPath, Paths.get(targetPath + "/" + dslPath.getFileName()));
    }


    private void createZipForPlugin(final String resourceRoot,
                                    File targetDir, String targetName) {

        try {
            final Archive.ArchiveBuilder packagedPluginBuilder = new Archive.ArchiveBuilder();
            Files.walkFileTree(temporaryDirectory.toPath().resolve(resourceRoot), new SimpleFileVisitor<Path>() {
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    if (file.toString().endsWith(".pyc")) {
                        return FileVisitResult.CONTINUE;
                    }
                    byte[] content = com.google.common.io.Files.toByteArray(file.toFile());
                    String targetFile = temporaryDirectory.toPath()
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

    private void copyDirectory(final Path source, final Path target) throws IOException {

        SimpleFileVisitor<Path> copyDirVisitor = new SimpleFileVisitor<Path>() {

            private StandardCopyOption copyOption = StandardCopyOption.REPLACE_EXISTING;

            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                Path targetPath = target.resolve(source.relativize(dir));
                if (!Files.exists(targetPath)) {
                    Files.createDirectory(targetPath);
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                Files.copy(file, target.resolve(source.relativize(file)), copyOption);
                return FileVisitResult.CONTINUE;
            }
        };
        Files.walkFileTree(source, copyDirVisitor);
    }
}
