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

import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.manager.dsl.config.JettyDSLImporterConfig;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.InetAddress;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Test for the dsl importer we use to import dsl and plugins.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@ContextConfiguration(classes = { DSLImporterTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class DSLImporterTest extends AbstractTestNGSpringContextTests {

    private static final String EXPECTED_PLUGIN_NAME = "python_webserver_installer.zip";
    private static final String EXPECTED_RELATIVE_DSL_PATH = "integration_phase3/integration-phase3.yaml";
    private static final String EXPECTED_RELATIVE_DSL_NO_PLUGINS_PATH = "noplugins/integration-phase3.yaml";

    /**
     * Test Config.
     */
    @Configuration
    @Import({
            TemporaryDirectoryConfig.class,
            JettyDSLImporterConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/fileserver/config/test.properties")
    static class Config extends TestConfig {

    }

    @Inject
    private DSLImporter dslImporter;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @NotEmpty
    @Value("${cosmo.plugin-config.dsl}")
    private String dslPath;

    @NotEmpty
    @Value("${cosmo.plugin-config.dsl-no-plugins}")
    private String dslPathNoPlugins;

    @Value("${cosmo.file-server.port}")
    private int port;

    @Test
    public void testImportDSLAsResource() throws Exception {

        String expectedFullDSLPath = "http://" + InetAddress.getLocalHost().getHostAddress() + ":" + port + "/" +
                EXPECTED_RELATIVE_DSL_PATH;

        String dslLocation = dslImporter.importDSL(dslPath);

        Path expectedResourceBase = Paths.get(temporaryDirectory.get().getAbsolutePath() + "/fileserver");

        Path pluginPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_PLUGIN_NAME);
        Path dslPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_RELATIVE_DSL_PATH);

        assertThat(pluginPath.toFile()).exists();
        assertThat(dslPath.toFile()).exists();
        assertThat(dslLocation).isEqualTo(expectedFullDSLPath);

    }

    @Test
    public void testImportDSLAsFullPath() throws Exception {

        String expectedFullDSLPath = "http://" + InetAddress.getLocalHost().getHostAddress() + ":" + port + "/" +
                EXPECTED_RELATIVE_DSL_PATH;

        Path fullPathToDSL = Paths.get(Resources.getResource(dslPath).getPath());

        String dslLocation = dslImporter.importDSL(fullPathToDSL);

        Path expectedResourceBase = Paths.get(temporaryDirectory.get().getAbsolutePath() + "/fileserver");

        Path pluginPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_PLUGIN_NAME);
        Path dslPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_RELATIVE_DSL_PATH);

        assertThat(pluginPath.toFile()).exists();
        assertThat(dslPath.toFile()).exists();
        assertThat(dslLocation).isEqualTo(expectedFullDSLPath);


    }

    @Test
    public void testImportDSLAsFullPathPointingToDirectory() throws Exception {


        int lastSeparator = dslPath.lastIndexOf("/");
        String dslParent = dslPath.substring(0, lastSeparator);

        String expectedFullDSLPath = "http://" + InetAddress.getLocalHost().getHostAddress() + ":" + port + "/" +
                EXPECTED_RELATIVE_DSL_PATH;

        Path fullPathToDSL = Paths.get(Resources.getResource(dslParent).getPath());

        String dslLocation = dslImporter.importDSL(fullPathToDSL);

        Path expectedResourceBase = Paths.get(temporaryDirectory.get().getAbsolutePath() + "/fileserver");

        Path pluginPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_PLUGIN_NAME);
        Path dslPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(), EXPECTED_RELATIVE_DSL_PATH);

        assertThat(pluginPath.toFile()).exists();
        assertThat(dslPath.toFile()).exists();
        assertThat(dslLocation).isEqualTo(expectedFullDSLPath);

    }

    @Test
    public void testImportDSLAsFullPathNoPlugins() throws Exception {


        String expectedFullDSLPath = "http://" + InetAddress.getLocalHost().getHostAddress() + ":" + port + "/" +
                EXPECTED_RELATIVE_DSL_NO_PLUGINS_PATH;

        Path fullPathToDSL = Paths.get(Resources.getResource(dslPathNoPlugins).getPath());

        String dslLocation = dslImporter.importDSL(fullPathToDSL);

        Path expectedResourceBase = Paths.get(temporaryDirectory.get().getAbsolutePath() + "/fileserver");

        Path dslPath = Paths.get(expectedResourceBase.toAbsolutePath().toString(),
                EXPECTED_RELATIVE_DSL_NO_PLUGINS_PATH);

        assertThat(dslPath.toFile()).exists();
        assertThat(dslLocation).isEqualTo(expectedFullDSLPath);

    }
}
