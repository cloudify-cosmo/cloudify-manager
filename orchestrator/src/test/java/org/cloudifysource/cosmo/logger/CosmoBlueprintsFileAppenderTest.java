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

package org.cloudifysource.cosmo.logger;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.collect.Maps;
import org.apache.log4j.Level;
import org.apache.log4j.Logger;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * @author Idan Moyal
 * @since 0.3
 */
@ContextConfiguration(classes = { CosmoBlueprintsFileAppenderTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class CosmoBlueprintsFileAppenderTest extends AbstractTestNGSpringContextTests {

    private final ObjectMapper mapper = new ObjectMapper();
    private final Logger logger = Logger.getLogger(getClass());
    private Level currentLevel;

    /**
     */
    @Configuration
    @Import({ TemporaryDirectoryConfig.class })
    static class Config extends TestConfig {
        @Inject
        private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

        @Bean(destroyMethod = "close")
        public CosmoBlueprintsFileAppender createWorkflowFileAppender() {
            CosmoBlueprintsFileAppender appender = new CosmoBlueprintsFileAppender(temporaryDirectory.get().toPath());
            appender.setName("test");
            appender.setThreshold(Level.DEBUG);
            appender.activateOptions();
            return appender;
        }
    }

    @BeforeMethod
    public void beforeMethod() {
        currentLevel = Logger.getRootLogger().getLevel();
        Logger.getRootLogger().setLevel(Level.DEBUG);
        logger.addAppender(cosmoBlueprintsFileAppender);
    }

    @AfterMethod
    public void afterMethod() {
        Logger.getRootLogger().setLevel(currentLevel);
        logger.removeAllAppenders();
    }

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @Inject
    private CosmoBlueprintsFileAppender cosmoBlueprintsFileAppender;

    @Test
    public void testLogWrittenToFile() throws IOException {
        Map<String, String> event = Maps.newHashMap();
        event.put("app", "my_app");
        logger.info(createJsonEvent(event));
        assertFileExists("my_app.log");
        assertFileContent("{\"app\":\"my_app\"}\n", "my_app.log");
    }

    @Test
    public void testLinesWrittenToFile() throws IOException {
        Map<String, String> event = Maps.newHashMap();
        event.put("app", "my_app");
        logger.info(createJsonEvent(event));
        event.put("test", "1234");
        logger.info(createJsonEvent(event));
        assertFileExists("my_app.log");
        assertFileContent("{\"app\":\"my_app\"}\n{\"app\":\"my_app\",\"test\":\"1234\"}\n", "my_app.log");
    }

    @Test
    public void testLinesWrittenForDifferentToDifferentFiles() throws IOException {
        Map<String, String> event1 = Maps.newHashMap();
        event1.put("app", "my_app1");
        logger.info(createJsonEvent(event1));
        Map<String, String> event2 = Maps.newHashMap();
        event2.put("deployment_id", "my_app2");
        logger.info(createJsonEvent(event2));
        assertFileExists("my_app1.log");
        assertFileContent("{\"app\":\"my_app1\"}\n", "my_app1.log");
        assertFileExists("my_app2.log");
        assertFileContent("{\"deployment_id\":\"my_app2\"}\n", "my_app2.log");
    }

    @Test
    public void testLogMessageWithoutJson() {
        logger.info("no json here");
    }

    private String createJsonEvent(Object obj) throws JsonProcessingException {
        return "event: " + mapper.writeValueAsString(obj);
    }

    private void assertFileContent(String expectedContent, String filename) throws IOException {
        String content = readLogFile(filename);
        content = content.replaceAll("\"timestamp\":\".*?\",", "");
        Assert.assertEquals(expectedContent.replace("\n", System.getProperty("line.separator")), content);
    }

    private void assertFileExists(String filename) {
        Path filePath = Paths.get(temporaryDirectory.get().toString(), filename);
        Assert.assertTrue(Files.exists(filePath));
    }

    private String readLogFile(String filename) throws IOException {
        Path logFile = Paths.get(temporaryDirectory.get().toString(), filename);
        return com.google.common.io.Files.toString(logFile.toFile(), Charset.defaultCharset());
    }

}
