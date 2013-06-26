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

import com.google.common.base.Charsets;
import com.google.common.collect.Maps;
import com.google.common.io.Files;
import org.testng.annotations.Test;

import java.io.File;
import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLPackagingTest {

    @Test
    public void testPackageProcessor() throws IOException {
        final String application = "definitions:\n" +
                "\timports:\n" +
                "\t\t- \"image-vm.yaml\"\n" +
                "\tservice_template:\n" +
                "\t\tvm_instance:\n" +
                "\t\t\tproperties:\n" +
                "\t\t\t\timage: \"arch-linux\"\n";
        final String vm = "definitions:\n" +
                "\ttypes:\n" +
                "\t\tvm:\n";
        final String imageVm = "definitions:\n" +
                "\timports:\n" +
                "\t\t- \"vm.yaml\"\n" +
                "\ttypes:\n" +
                "\t\tcosmo.types.image_vm:\n" +
                "\t\t\tderived_from: \"cosmo.types.vm\"\n" +
                "\t\t\tproperties:\n" +
                "\t\t\t\timage: \"\"\n" +
                "\t\t\tinterfaces:\n" +
                "\tinterfaces:\n" +
                "\t\tcloud_driver:\n" +
                "\t\t\toperations:\n" +
                "\t\t\t\t- \"provision\"\n" +
                "\t\t\t\t- \"terminate\"\n" +
                "\tartifacts:\n" +
                "\t\tplugin:\n" +
                "\t\t\tproperties:\n" +
                "\t\t\t\tinterface: \"\"\n" +
                "\t\t\t\turl: \"\"\n" +
                "\t\tcosmo_cloud_driver:\n" +
                "\t\t\tderived_from: \"plugin\"\n" +
                "\t\t\tproperties:\n" +
                "\t\t\t\tinterface: \"cloud_driver\"\n" +
                "\t\t\t\turl: \"http://localhost:8080/cosmo_cloud_driver.zip\"\n" +
                "\tplans:\n" +
                "\t\tcosmo.types.image_vm:\n" +
                "\t\t\tinit:\n" +
                "\t\t\t\tradial: |\n" +
                "\t\t\t\t\tdefine init\n" +
                "\t\t\t\t\t\texecute_operation operation: 'provision'\n";
        final DSLPackage dslPackage = new DSLPackage.DSLPackageBuilder()
                .addFile("application.yaml", application)
                .addFile("definitions/vm.yaml", vm)
                .addFile("definitions/image-vm.yaml", imageVm)
                .build();

        final File tempDir = Files.createTempDir();
        try {
            final File packageFile = new File(tempDir, "cosmo-application.zip");
            dslPackage.write(packageFile);
            assertThat(packageFile.exists()).isTrue();

            final ExtractedDSLPackageDetails result = DSLPackageProcessor.process(packageFile, tempDir);
            final Path expectedDslPath = Paths.get(tempDir.toString(), "application.yaml");
            assertThat(result.getDslPath()).isEqualTo(expectedDslPath);
            assertThat(result.getPackageLocation()).isEqualTo(tempDir.toString());

            final String dsl = Files.toString(result.getDslPath().toFile(), Charsets.UTF_8);
            assertThat(dsl).isEqualTo(application);

        } finally {
            deleteDirectory(tempDir.toPath());
        }
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
        } catch (IOException e) {
        }
    }


}
