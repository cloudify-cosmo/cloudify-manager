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

import com.google.common.collect.Maps;
import com.google.common.io.Files;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.File;
import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Path;
import java.util.Map;


/**
 * Creates a new {@link org.cloudifysource.cosmo.manager.config.TemporaryDirectoryConfig.TemporaryDirectory}.
 *
 * @author Idan Moyal
 * @since 0.1
 */
@Configuration
public class TemporaryDirectoryConfig {

    @Bean(destroyMethod = "close")
    public TemporaryDirectory temporaryDirectory() {
        return new TemporaryDirectory();
    }

    /**
     */
    public static class TemporaryDirectory {

        private File directory;

        public TemporaryDirectory() {
            this.directory = Files.createTempDir();
        }

        public void close() {
            deleteDirectory(directory.toPath());
        }

        public File get() {
            return directory;
        }

        private void deleteDirectory(Path root) {
            Map<String, Object> env = Maps.newHashMap();
            env.put("create", "false");
            try (DirectoryStream<Path> directoryStream = java.nio.file.Files.newDirectoryStream(root)) {
                for (Path path : directoryStream) {
                    if (java.nio.file.Files.isDirectory(path)) {
                        deleteDirectory(path);
                    }
                    java.nio.file.Files.deleteIfExists(path);
                }
                java.nio.file.Files.deleteIfExists(root);
            } catch (IOException ignored) {
            }

        }

    }
}
