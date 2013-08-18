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
 *******************************************************************************/

package org.cloudifysource.cosmo.orchestrator.workflow;

import com.google.common.base.Charsets;
import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.dsl.packaging.DSLPackageProcessor;
import org.cloudifysource.cosmo.dsl.packaging.ExtractedDSLPackageDetails;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.orchestrator.workflow.config.DefaultRuoteWorkflowConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.StateCacheValue;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.MockCeleryTaskWorker;
import org.cloudifysource.cosmo.tasks.TaskReceivedListener;
import org.cloudifysource.cosmo.tasks.config.MockCeleryTaskWorkerConfig;
import org.cloudifysource.cosmo.tasks.config.MockTaskExecutorConfig;
import org.cloudifysource.cosmo.utils.Archive;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { RuoteExecutePlanTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecutePlanTest extends AbstractTestNGSpringContextTests {

    private static final String CLOUDIFY_MANAGEMENT = "cloudify.management";
    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    /**
     */
    @Configuration
    @Import({
            DefaultRuoteWorkflowConfig.class,
            RuoteRuntimeConfig.class,
            TemporaryDirectoryConfig.class,
            MockTaskExecutorConfig.class,
            MockCeleryTaskWorkerConfig.class,
            StateCacheConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Inject
    private RuoteWorkflow ruoteWorkflow;

    @Inject
    private StateCache stateCache;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @Inject
    private MockCeleryTaskWorker worker;


    @Test(timeOut = 30000)
    public void testPlanExecutionDslWithBaseImports() throws IOException, InterruptedException {
        String dslFile = "org/cloudifysource/cosmo/dsl/dsl-with-base-imports.yaml";
        String machineId = "mysql_template.mysql_host";
        String databaseId = "mysql_template.mysql_database_server";
        reachable("mysql_template.mysql_schema");
        OperationsDescriptor[] descriptors = {
            new OperationsDescriptor(
                CLOUDIFY_MANAGEMENT,
                "cloudify.tosca.artifacts.plugin.host_provisioner",
                new String[]{"provision", "start"}),
            new OperationsDescriptor(
                machineId,
                "cloudify.tosca.artifacts.plugin.middleware_component_installer",
                new String[]{"install", "start"}),
            new OperationsDescriptor(
                machineId,
                "cloudify.tosca.artifacts.plugin.app_module_installer",
                new String[]{"deploy", "start"})
        };
        testPlanExecution(dslFile, new String[] {machineId, databaseId}, descriptors);
    }

    @Test(timeOut = 30000)
    public void testPlanExecutionDslWithBaseImportsDependencies() throws IOException, InterruptedException {
        String dslFile = "org/cloudifysource/cosmo/dsl/dsl-with-base-imports.yaml";
        String machineId = "mysql_template.mysql_host";
        String databaseId = "mysql_template.mysql_database_server";
        reachable("mysql_template.mysql_schema");
        OperationsDescriptor[] descriptors = {
            new OperationsDescriptor(
                    CLOUDIFY_MANAGEMENT,
                    "cloudify.tosca.artifacts.plugin.host_provisioner",
                    new String[]{"provision", "start"}),
            new OperationsDescriptor(
                    machineId,
                    "cloudify.tosca.artifacts.plugin.middleware_component_installer",
                    new String[]{"install", "start"}),
            new OperationsDescriptor(
                    machineId,
                    "cloudify.tosca.artifacts.plugin.app_module_installer",
                    new String[]{"deploy", "start"})
        };
        testPlanExecution(dslFile, new String[] {machineId, databaseId}, descriptors, true);
    }

    /**
     * For POC purposes - this test should be disabled.
     */
    @Test(timeOut = 60000, enabled = false)
    public void testPlanExecutionPoc() throws IOException, InterruptedException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/poc/poc-dsl1.yaml";
        String machineId = "mysql_template.mysql_host";
        String databaseId = "mysql_template.mysql_database_server";
        String schemaId = "mysql_template.mysql_schema";

        final Map<String, Object> fields = Maps.newHashMap();
        String dslLocation;
        if (Files.exists(Paths.get(dslFile))) {
            dslLocation = dslFile;
        } else {
            dslLocation = Resources.getResource(dslFile).getFile();
        }
        fields.put("dsl", dslLocation);

        final Object wfid = ruoteWorkflow.asyncExecute(fields);

        Thread.sleep(10000);
        reachable(machineId);
        Thread.sleep(10000);
        reachable(databaseId);
        Thread.sleep(5000);
        reachable(schemaId);

        ruoteRuntime.waitForWorkflow(wfid);
    }


    @Test(timeOut = 30000)
    public void testPlanExecutionFromPackage() throws IOException, InterruptedException {

        reachable("package_template.package_vm");

        URL resource = Resources.getResource("org/cloudifysource/cosmo/dsl/unit/packaging/basic-packaging.yaml");
        String dsl = Resources.toString(
                resource, Charsets.UTF_8);
        Archive dslPackage = new Archive.ArchiveBuilder()
                .addFile("app.yaml", dsl)
                .build();
        final Path packagePath = Paths.get(temporaryDirectory.get().getCanonicalPath(), "app.zip");
        dslPackage.write(packagePath.toFile());

        final ExtractedDSLPackageDetails processed =
                DSLPackageProcessor.process(packagePath.toFile(), temporaryDirectory.get());

        OperationsDescriptor[] descriptors = {
            new OperationsDescriptor(
                    CLOUDIFY_MANAGEMENT,
                    "provisioner_plugin",
                    new String[] {"start"})
        };

        testPlanExecution(processed.getDslPath().toString(), null, descriptors);
    }

    @Test(timeOut = 30000)
    public void testPlanExecutionFromPackageWithImports() throws IOException, InterruptedException {

        reachable("test_template.test_vm00");
        reachable("test_template.test_vm1");
        reachable("test_template.test_vm2");
        reachable("test_template.test_vm03");
        reachable("test_template.test_vm04");
        reachable("test_template.test_vm05");

        final String root = "org/cloudifysource/cosmo/dsl/unit/packaging/imports/";
        Archive dslPackage = new Archive.ArchiveBuilder()
                .addFile("app.yaml", getResourceAsString(root + "packaging-with-imports.yaml"))
                .addFile("definitions/packaging-with-imports0.yaml",
                        getResourceAsString(root + "packaging-with-imports0.yaml"))
                .addFile("definitions/relative_from_base/packaging-with-imports1.yaml",
                        getResourceAsString(root + "packaging-with-imports1.yaml"))
                .addFile("definitions/fixed_from_base/packaging-with-imports2.yaml",
                        getResourceAsString(root + "packaging-with-imports2.yaml"))
                .addFile("definitions/packaging-with-imports3.yaml",
                        getResourceAsString(root + "packaging-with-imports3.yaml"))
                .addFile("definitions/relative_path/packaging-with-imports4.yaml",
                        getResourceAsString(root + "packaging-with-imports4.yaml"))
                .addFile("definitions/fixed_path/packaging-with-imports5.yaml",
                        getResourceAsString(root + "packaging-with-imports5.yaml"))
                .build();
        final Path packagePath = Paths.get(temporaryDirectory.get().getCanonicalPath(), "app-imports.zip");
        dslPackage.write(packagePath.toFile());

        final ExtractedDSLPackageDetails processed =
                DSLPackageProcessor.process(packagePath.toFile(), temporaryDirectory.get());

        String[] operations =
                new String[]{"operation0", "operation1", "operation2", "operation3", "operation4", "operation5"};
        OperationsDescriptor[] descriptors = {new OperationsDescriptor(
                CLOUDIFY_MANAGEMENT,
                "provisioner_plugin",
                operations)};

        testPlanExecution(processed.getDslPath().toString(), null, descriptors);
    }


    @Test(timeOut = 30000)
    public void testPlanExecutionWithOverriddenGlobalPlan() throws IOException, InterruptedException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/global_plan/dsl-with-with-full-global-plan.yaml";
        OperationsDescriptor descriptor = new OperationsDescriptor(
                CLOUDIFY_MANAGEMENT,
                "cloudify.tosca.artifacts.plugin.host_provisioner",
                new String[]{"provision", "start", "provision", "start"});
        OperationsDescriptor[] descriptors = {descriptor};
        testPlanExecution(dslFile, null, descriptors);
    }

    private void testPlanExecution(
            String dslFile,
            String[] reachableIds,
            OperationsDescriptor[] expectedOperations) throws IOException, InterruptedException {
        testPlanExecution(dslFile, reachableIds, expectedOperations, false);
    }

    private void testPlanExecution(
            String dslFile,
            String[] reachableIds,
            final OperationsDescriptor[] expectedOperations,
            final boolean assertExecutionOrder) throws IOException,
            InterruptedException {

        String dslLocation;
        if (Files.exists(Paths.get(dslFile))) {
            dslLocation = dslFile;
        } else {
            dslLocation = Resources.getResource(dslFile).getFile();
        }
        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", dslLocation);

        final List<String> expectedTasks = Lists.newArrayList();
        final List<String> expectedTasksWithSeparator = Lists.newArrayList();
        for (OperationsDescriptor pluginOperations : expectedOperations) {
            for (String operationName : pluginOperations.operations) {
                String expectedTask = String.format("cosmo.%s.tasks.%s", pluginOperations.pluginName, operationName);
                expectedTasks.add(expectedTask);
                expectedTasksWithSeparator.add(expectedTask);
            }
            expectedTasksWithSeparator.add("");
        }

        final List<String> executions = Lists.newArrayList();
        TaskReceivedListener listener = new TaskReceivedListener() {
            @Override
            public synchronized Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                if (taskName.endsWith("verify_plugin") || taskName.endsWith("reload_riemann_config")) {
                    return "True";
                }
                if (assertExecutionOrder) {
                    executions.add(taskName);
                    if (expectedTasksWithSeparator.isEmpty()) {
                        return null;
                    }
                    if (Objects.equal(expectedTasksWithSeparator.get(0), taskName)) {
                        expectedTasksWithSeparator.remove(0);
                        if (expectedTasksWithSeparator.get(0).length() == 0) {
                            String nodeId = kwargs.get("__cloudify_id").toString();
                            reachable(nodeId);
                            expectedTasksWithSeparator.remove(0);
                        }
                    }
                }
                return null;
            }
        };

        int latchCount = 0;
        for (OperationsDescriptor descriptor : expectedOperations) {
            latchCount += descriptor.operations.length;
        }
        final CountDownLatch latch = new CountDownLatch(latchCount);
        for (OperationsDescriptor descriptor : expectedOperations) {
            worker.addListener(descriptor.target,
                    new PluginExecutionMessageConsumerListener(latch, descriptor.operations, !assertExecutionOrder));
            worker.addListener(descriptor.target, listener);
        }

        final Object wfid = ruoteWorkflow.asyncExecute(fields);

        Thread.sleep(100);
        if (reachableIds != null && !assertExecutionOrder) {
            for (String reachableId : reachableIds) {
                reachable(reachableId);
            }
        }

        ruoteRuntime.waitForWorkflow(wfid);
        latch.await();

        if (assertExecutionOrder) {
            assertThat(executions).isEqualTo(expectedTasks);
            assertThat(expectedTasksWithSeparator).isEmpty();
        }
    }

    @Test(timeOut = 30000)
    public void testRuntimePropertiesInjection() throws IOException, InterruptedException {
        final String dslFile = "org/cloudifysource/cosmo/dsl/dsl-with-base-imports.yaml";
        final String machineId = "mysql_template.mysql_host";
        final String ip = "10.0.0.1";

        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", Resources.getResource(dslFile).getFile());
        ruoteWorkflow.asyncExecute(fields);

        final CountDownLatch latch = new CountDownLatch(1);

        worker.addListener(machineId, new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                if (taskName.endsWith("verify_plugin")) {
                    return "True";
                }
                Map<?, ?> runtimeProperties = (Map<?, ?>) kwargs.get("cloudify_runtime");
                if (runtimeProperties.containsKey(machineId)) {
                    Map<?, ?> machineProperties = (Map<?, ?>) runtimeProperties.get(machineId);
                    if (Objects.equal(ip, machineProperties.get("ip"))) {
                        latch.countDown();
                    }
                }
                return null;
            }
        });

        discoveredIpAddress(machineId, ip);
        reachable(machineId);
        latch.await();
    }

    @Test(timeOut = 30000)
    public void testHostExtractionFromRelationships() throws InterruptedException {
        final String dslFile = "org/cloudifysource/cosmo/dsl/unit/relationships/dsl-for-host-extraction.yaml";
        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", Resources.getResource(dslFile).getFile());
        Object wfid = ruoteWorkflow.asyncExecute(fields);

        final String serviceTemplate = "service_template";
        final String host1Id = String.format("%s.%s", serviceTemplate, "host1");
        final String host2Id = String.format("%s.%s", serviceTemplate, "host2");
        final String webServerId = String.format("%s.%s", serviceTemplate, "webserver1");
        final String webApplicationId = String.format("%s.%s", serviceTemplate, "webapplication1");

        reachable(host1Id);
        reachable(host2Id);
        reachable(webServerId);
        reachable(webApplicationId);

        final Object[][] expectedTasks =
        {
            {
                CLOUDIFY_MANAGEMENT,
                "cosmo.test.host.provisioner2.tasks.provision",
                host2Id,
                new CountDownLatch(1)
            },
            {
                host1Id,
                "cosmo.test.host.provisioner.tasks.provision",
                host1Id,
                new CountDownLatch(1)
            },
            {
                host1Id,
                "cosmo.cloudify.tosca.artifacts.plugin.middleware_component.installer.tasks.install",
                webServerId,
                new CountDownLatch(1)
            },
            {
                host1Id,
                "cosmo.cloudify.tosca.artifacts.plugin.app_module.installer.tasks.deploy",
                webApplicationId,
                new CountDownLatch(1)
            }
        };

        final TaskReceivedListener listener = new TaskReceivedListener() {
            public synchronized Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                for (Object[] expectedTask : expectedTasks) {
                    if (expectedTask[0].equals(target) && expectedTask[1].equals(taskName) &&
                        expectedTask[2].equals(kwargs.get("__cloudify_id"))) {
                        ((CountDownLatch) expectedTask[3]).countDown();
                    }
                }
                return "True";
            }
        };

        worker.addListener(CLOUDIFY_MANAGEMENT, listener);
        worker.addListener(host1Id, listener);
        worker.addListener(host2Id, listener);

        ruoteRuntime.waitForWorkflow(wfid);

        for (Object[] expectedTask : expectedTasks) {
            ((CountDownLatch) expectedTask[3]).await();
        }
    }

    /**
     */
    static class TaskDescriptor {


        TaskDescriptor(String endsWith, String result, Map<String, String> expectedInArgs,
                       Set<String> notExpectedInArgs, int expectedIndex,
                       String expectedTarget) {
            this.endsWith = endsWith;
            this.result = result;
            this.expectedInArgs = expectedInArgs;
            this.notExpectedInArgs = notExpectedInArgs;
            this.expectedIndex = expectedIndex;
            this.expectedTarget = expectedTarget;
        }

        String endsWith;
        String result;
        Map<String, String> expectedInArgs;
        Set<String> notExpectedInArgs;
        int expectedIndex;
        String expectedTarget;
        CountDownLatch latch = new CountDownLatch(1);
    }

    private static TaskDescriptor buildRelationshipsTemplateTaskDescriptor(
        String endsWith,
        String result,
        int maxExpectedResult,
        int index,
        String target
    ) {
        Map<String, String> expectedProps = Maps.newHashMap();
        expectedProps.put("host_prop1", "host_value1");
        expectedProps.put("webserver_prop1", "webserver_value1");
        for (int i = 1; i <= maxExpectedResult; i++) {
            expectedProps.put("result" + i + "", "result" + i + "_value");
        }
        Set<String> notExpectedProps = Sets.newHashSet();
        for (int i = maxExpectedResult + 1; i <= 6; i++) {
            notExpectedProps.add("result" + i + "");
        }
        return new TaskDescriptor(endsWith, result, expectedProps, notExpectedProps, index, target);
    }

    @Test(timeOut = 30000_000)
    public void testRelationshipTemplates() throws IOException, InterruptedException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/relationship_templates/" +
                "dsl-with-relationship-templates-ruote.yaml";
        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", Resources.getResource(dslFile).getFile());
        Object wfid = ruoteWorkflow.asyncExecute(fields);

        final String hostId = "service_template.host";
        final String webServerId = "service_template.webserver";

        final TaskDescriptor[] descriptors = new TaskDescriptor[] {
            buildRelationshipsTemplateTaskDescriptor(".operation1", "result1_value", 0, 0, hostId),
            buildRelationshipsTemplateTaskDescriptor(".operation2", "result2_value", 1, 1, CLOUDIFY_MANAGEMENT),
            buildRelationshipsTemplateTaskDescriptor(".operation3", "", 2, 2, hostId),
            buildRelationshipsTemplateTaskDescriptor(".pause", "result3_value", 2, 3, CLOUDIFY_MANAGEMENT),
            buildRelationshipsTemplateTaskDescriptor(".operation4", "result4_value", 3, 4, hostId),
            buildRelationshipsTemplateTaskDescriptor(".operation5", "result5_value", 4, 5, CLOUDIFY_MANAGEMENT),
            buildRelationshipsTemplateTaskDescriptor(".operation6", "", 5, 6, hostId),
            buildRelationshipsTemplateTaskDescriptor(".operation7", "result6_value", 5, 7, CLOUDIFY_MANAGEMENT),
        };

        final AtomicInteger currentIndex = new AtomicInteger(0);
        final TaskReceivedListener listener = new TaskReceivedListener() {

            public synchronized Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                for (TaskDescriptor descriptor : descriptors) {
                    if (taskName.endsWith(descriptor.endsWith)) {
                        boolean valid = true;
                        for (Map.Entry<String, String> entry : descriptor.expectedInArgs.entrySet()) {
                            if (!entry.getValue().equals(kwargs.get(entry.getKey()))) {
                                valid = false;
                            }
                        }
                        for (String notExpected : descriptor.notExpectedInArgs) {
                            if (kwargs.containsKey(notExpected)) {
                                valid = false;
                            }
                        }
                        if (!target.equals(descriptor.expectedTarget)) {
                            valid = false;
                        }
                        if (descriptor.expectedIndex != currentIndex.get()) {
                            valid = false;
                        }
                        if (valid) {
                            descriptor.latch.countDown();
                        }
                        currentIndex.incrementAndGet();
                        return descriptor.result;
                    }
                }

                // For verify_plugin
                return "True";
            }
        };

        worker.addListener(CLOUDIFY_MANAGEMENT, listener);
        worker.addListener(hostId, listener);

        reachable(hostId);
        reachable(webServerId);

        ruoteRuntime.waitForWorkflow(wfid);

        for (TaskDescriptor taskDescriptor : descriptors) {
            taskDescriptor.latch.await();
        }
    }

    @Test(timeOut = 60000)
    public void testExecuteOperationFailure() {
        String radial = "define workflow\n" +
                "  execute_operation operation: 'op'";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, ruoteRuntime);
        Map<String, Object> plugin = Maps.newHashMap();
        plugin.put("agent_plugin", "true");
        Map<String, Object> plugins = Maps.newHashMap();
        plugins.put("plugin", plugin);
        Map<String, Object> operations = Maps.newHashMap();
        operations.put("op", "plugin");
        Map<String, Object> node = Maps.newHashMap();
        node.put("id", "id");
        node.put("host_id", "host");
        node.put("operations", operations);
        node.put("plugins", plugins);
        node.put("properties", Maps.newHashMap());
        Map<String, Object> fields = Maps.newHashMap();
        fields.put("node", node);


        final AtomicInteger counter = new AtomicInteger(0);
        TaskReceivedListener listener = new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                System.out.println(
                        "-- " + counter.get() + " received task: " + target + ", " + taskName + ", " + kwargs);
                if (taskName.contains("verify_plugin")) {
                    if (counter.get() < 2) {
                        counter.incrementAndGet();
                        return "False";
                    }
                }
                return "True";
            }
        };

        worker.addListener("host", listener);

        Object wfid = workflow.asyncExecute(fields);
        ruoteRuntime.waitForWorkflow(wfid);
    }

    @Test(timeOut = 30000)
    public void testExecuteOperation() throws InterruptedException {
        final String dslFile = "org/cloudifysource/cosmo/dsl/unit/plugins/target/plugin-targets.yaml";
        final String machineId = "plugins_template.host_template";
        final String remotePluginTarget = "cloudify.management";
        final String agentTaskPrefix = "cosmo.cloudify.tosca.artifacts.plugin.middleware_component_installer.tasks";
        final String remoteTaskPrefix = "cosmo.cloudify.tosca.artifacts.plugin.host_provisioner.tasks";
        final String pluginInstallerPrefix = "cosmo.cloudify.tosca.artifacts.plugin.plugin_installer.tasks";

        reachable("plugins_template.server_template");

        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", Resources.getResource(dslFile).getFile());
        Object wfid = ruoteWorkflow.asyncExecute(fields);

        final CountDownLatch latch = new CountDownLatch(6);

        final List<String> executedTasks = Lists.newArrayList();

        // Execution order should be:
        // 0-verify [management]
        // 1-provision
        // 2-verify [agent]
        // 3-install
        // 4-verify [agent]
        // 5-start
        TaskReceivedListener listener = new TaskReceivedListener() {
            @Override
            public synchronized Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                final int executedTasksCount = executedTasks.size();
                if (taskName.startsWith(pluginInstallerPrefix)) {
                    assertThat(kwargs).containsKey("plugin_name");
                    assertThat(executedTasksCount).isIn(0, 2, 4);
                    String pluginName = kwargs.get("plugin_name").toString();
                    if (executedTasksCount == 0) {
                        assertThat(target).isEqualTo(remotePluginTarget);
                        assertThat(pluginName).isEqualTo(remoteTaskPrefix);
                    } else if (executedTasksCount == 2 || executedTasksCount == 4) {
                        assertThat(target).isEqualTo(machineId);
                        assertThat(pluginName).isEqualTo(agentTaskPrefix);
                    }
                    latch.countDown();
                    executedTasks.add(taskName);
                    return taskName.contains("verify_plugin") ? "True" : "False";
                } else if (taskName.startsWith(remoteTaskPrefix)) {
                    assertThat(target).isEqualTo(remotePluginTarget);
                    assertThat(executedTasksCount).isEqualTo(1);
                    assertThat(taskName).endsWith(".provision");
                    latch.countDown();
                    executedTasks.add(taskName);
                    // in this stage make the host reachable so its dependent nodes would start firing tasks.
                    reachable(machineId);
                } else if (taskName.startsWith(agentTaskPrefix)) {
                    assertThat(target).isEqualTo(machineId);
                    assertThat(executedTasksCount).isIn(3, 5);
                    if (executedTasksCount == 3) {
                        assertThat(taskName).endsWith(".install");
                    } else {
                        assertThat(taskName).endsWith(".start");
                    }
                    latch.countDown();
                    executedTasks.add(taskName);
                }
                return null;
            }
        };

        worker.addListener(machineId, listener);
        worker.addListener(remotePluginTarget, listener);
        worker.addListener(machineId, listener);

        ruoteRuntime.waitForWorkflow(wfid);

        latch.await();

        assertThat(executedTasks.size()).isEqualTo(6);
    }

    private String getResourceAsString(String resourceName) {
        final URL resource = Resources.getResource(resourceName);
        try {
            return Resources.toString(resource, Charsets.UTF_8);
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    private void reachable(String nodeId) {
        Preconditions.checkNotNull(nodeId);
        stateCache.put(nodeId, "reachable", new StateCacheValue("true"));
    }

    private void discoveredIpAddress(String nodeId, String ipAddress) {
        Preconditions.checkNotNull(nodeId);
        Preconditions.checkNotNull(ipAddress);
        stateCache.put(nodeId, "ip", new StateCacheValue(ipAddress));
    }

    /**
     */
    private static class OperationsDescriptor {
        final String target;
        final String pluginName;
        final String[] operations;
        private OperationsDescriptor(String target, String pluginName, String[] operations) {
            this.target = target;
            this.pluginName = pluginName;
            this.operations = operations;
        }
    }

    /**
     */
    private static class PluginExecutionMessageConsumerListener implements TaskReceivedListener {
        private CountDownLatch latch;
        private boolean removeExecutedOperations;
        private List<String> operations;
        PluginExecutionMessageConsumerListener(CountDownLatch latch,
                                               String[] operations,
                                               boolean removeExecutedOperations) {
            this.latch = latch;
            this.removeExecutedOperations = removeExecutedOperations;
            this.operations = Lists.newLinkedList(Arrays.asList(operations));
        }

        @Override
        public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
            String operationName = extractOperationName(taskName);
            for (Iterator<String> iterator = operations.iterator(); iterator.hasNext();) {
                String expectedOperation =  iterator.next();
                if (operationName.equals(expectedOperation)) {
                    latch.countDown();
                    if (removeExecutedOperations) {
                        iterator.remove();
                    }
                    break;
                }
            }
            return null;
        }
    }

    private static String extractOperationName(String taskName) {
        String[] splitName = taskName.split("\\.");
        return splitName[splitName.length - 1];
    }

}
