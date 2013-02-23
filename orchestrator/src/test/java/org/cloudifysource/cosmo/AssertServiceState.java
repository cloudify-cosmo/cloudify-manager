package org.cloudifysource.cosmo;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.StartAgentTask;
import org.cloudifysource.cosmo.agent.tasks.StartMachineTask;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.testng.Assert;

import java.net.URI;
import java.util.Map;

import static org.cloudifysource.cosmo.AssertServiceState.assertServiceInstalledWithOneInstance;

public class AssertServiceState {

    private AssertServiceState() { }

    public static void assertServiceInstalledWithOneInstance(MockManagement management, String serviceName) {
        int zeroMachineRestarts = 0;
        int zeroAgentRestarts = 0;
        assertServiceInstalledWithOneInstance(management, serviceName, zeroAgentRestarts, zeroMachineRestarts);
    }

    public static void assertSingleServiceInstance(MockManagement management, String serviceName) {
        final int zeroAgentRestarts = 0;
        final int zeroMachineRestarts = 0;
        assertSingleServiceInstance(management, serviceName, zeroAgentRestarts, zeroMachineRestarts);
    }

    public static void assertSingleServiceInstance(
            MockManagement management, String serviceName,
            int numberOfAgentRestarts, int numberOfMachineRestarts) {

        Assert.assertEquals(management.getDeploymentPlan().getServices().size(), 1);
        Assert.assertEquals(
                Iterables.size(getAgentIds(management)), 1, "Expected 1 agent id, " +
                "instead found: "+ getAgentIds(management));
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(management, serviceName)),1);
        assertServiceInstalledWithOneInstance(
                management, serviceName, 
                numberOfAgentRestarts, numberOfMachineRestarts);
    }

    private static void assertServiceInstalledWithOneInstance(
            MockManagement management, String serviceName,
            int numberOfAgentRestarts, int numberOfMachineRestarts) {
        
        final URI serviceId = management.getServiceId(serviceName);
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
        final ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
        TaskConsumerHistory instanceTasksHistory = getTasksHistory(management, instanceId);
        Assert.assertEquals(Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), new Predicate<Task>() {

            @Override
            public boolean apply(Task task) {
                if (task instanceof ServiceInstanceTask) {
                    return ((ServiceInstanceTask)task).getLifecycle().equals("service_started");
                }
                return false;
            }
        }))
                ,1+numberOfMachineRestarts);

        final URI agentId = instanceState.getAgentId();
        Assert.assertEquals(instanceState.getServiceId(), serviceId);
        Assert.assertTrue(instanceState.isLifecycle("service_started"));

        final AgentState agentState = management.getAgentState(agentId);
        Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
        Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
        Assert.assertEquals(agentState.getNumberOfAgentRestarts(), numberOfAgentRestarts);
        Assert.assertEquals(agentState.getNumberOfMachineRestarts(), numberOfMachineRestarts);

        TaskConsumerHistory agentTasksHistory = getTasksHistory(management, agentId);
        Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartMachineTask.class)),1+numberOfMachineRestarts);
        Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartAgentTask.class)),1+numberOfMachineRestarts);

        final ServiceGridDeploymentPlan deploymentPlan = management.getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
        final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId).getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private static TaskConsumerHistory getTasksHistory(MockManagement management, final URI stateId) {
        final URI tasksHistoryId = ServiceUtils.toTasksHistoryId(stateId);
        EtagState<TaskConsumerHistory> etagState = management.getStateReader()
                .get(tasksHistoryId, TaskConsumerHistory.class);
        Preconditions.checkNotNull(etagState);
        return etagState.getState();
    }

    public static Iterable<URI> getServiceInstanceIds(MockManagement management, String serviceName) {
        return getStateIdsStartingWith(management, StreamUtils.newURI(management.getStateServerUri()
                + "services/" + serviceName + "/instances/"));
    }

    private static Iterable<URI> getStateIdsStartingWith(MockManagement management, final URI uri) {
        return Iterables.filter(
                management.getStateReader().getElementIdsStartingWith(uri),
                new Predicate<URI>(){

                    @Override
                    public boolean apply(URI stateId) {
                        return stateId.toString().endsWith("/");
                    }});
    }


    public static Iterable<URI> getAgentIds(MockManagement management) {
        final URI agentsPrefix = StreamUtils.newURI(management.getStateServerUri() + "agents/");
        return getStateIdsStartingWith(management, agentsPrefix);
    }

    public static void assertTwoTomcatInstances(
            MockManagement management, 
            Map<URI,Integer> numberOfAgentRestartsPerAgent, 
            Map<URI,Integer> numberOfMachineRestartsPerAgent) {
        final URI serviceId = management.getServiceId("tomcat");
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()), 2);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        Iterable<URI> instanceIds = getStateIdsStartingWith(management, StreamUtils.newURI(management
                .getStateServerUri()
                + "services/tomcat/instances/"));
        Assert.assertEquals(Iterables.size(instanceIds),2);

        final ServiceGridDeploymentPlan deploymentPlan = management.getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);

        Iterable<URI> agentIds = getAgentIds(management);
        int numberOfAgents = Iterables.size(agentIds);
        Assert.assertEquals(numberOfAgents, 2);
        for (int i = 0 ; i < numberOfAgents; i++) {

            URI agentId = Iterables.get(agentIds, i);
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
            Assert.assertEquals(agentState.getNumberOfAgentRestarts(), (int) numberOfAgentRestartsPerAgent.get(agentId));
            Assert.assertEquals(agentState.getNumberOfMachineRestarts(), (int) numberOfMachineRestartsPerAgent.get(agentId));
            URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
            Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            Assert.assertEquals(instanceState.getServiceId(), serviceId);
            Assert.assertEquals(instanceState.getAgentId(), agentId);
            Assert.assertTrue(instanceState.isLifecycle("service_started"));
            Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        }
    }

    public static void assertTwoTomcatInstances(MockManagement management) {
        assertTwoTomcatInstances(management, expectedBothAgentsNotRestarted(management), 
                expectedBothMachinesNotRestarted(management));
    }

    public static ImmutableMap<URI, Integer> expectedBothAgentsNotRestarted(MockManagement management) {
        return ImmutableMap.<URI,Integer>builder()
                .put(management.getAgentId(0), 0)
                .put(management.getAgentId(1), 0)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedBothMachinesNotRestarted(MockManagement management) {
        return ImmutableMap.<URI,Integer>builder()
                .put(management.getAgentId(0), 0)
                .put(management.getAgentId(1), 0)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedAgentZeroNotRestartedAgentOneRestarted(MockManagement 
                                                                                                    management) {
        return ImmutableMap.<URI,Integer>builder()
                .put(management.getAgentId(0), 0)
                .put(management.getAgentId(1), 1)
                .build();
    }


    public static void assertTomcatUninstalledGracefully(MockManagement management) {
        boolean instanceUnreachable = false;
        assertTomcatUninstalled(management, instanceUnreachable);
    }

    public static void assertTomcatUninstalledUnreachable(MockManagement management) {
        boolean instanceUnreachable = true;
        assertTomcatUninstalled(management, instanceUnreachable);
    }

    private static void assertTomcatUninstalled(MockManagement management, boolean instanceUnreachable) {
        final URI serviceId = management.getServiceId("tomcat");
        Assert.assertFalse(management.getDeploymentPlan().isServiceExists(serviceId));
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED));

        for (URI instanceId: getServiceInstanceIds(management, "tomcat")) {
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            if (instanceUnreachable) {
                Assert.assertTrue(instanceState.isUnreachable());
            }
            else {
                Assert.assertTrue(instanceState.isLifecycle("service_cleaned"));
            }
            URI agentId = instanceState.getAgentId();
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertTrue(agentState.isProgress(AgentState.Progress.MACHINE_TERMINATED));
        }
    }

    public static void assertOneTomcatInstance(MockManagement management) {
        assertSingleServiceInstance(management, "tomcat");
    }

    public static void assertTomcatScaledInFrom2To1(MockManagement management) {
        assertServiceInstalledWithOneInstance(management, "tomcat");
        Assert.assertTrue(management.getAgentState(management.getAgentId(0))
                .isProgress(AgentState.Progress.AGENT_STARTED));
        Assert.assertTrue(management.getAgentState(management.getAgentId(1))
                .isProgress(AgentState.Progress.MACHINE_TERMINATED));
        Assert.assertTrue(management.getServiceInstanceState(management.getServiceInstanceId("tomcat", 0))
                .isLifecycle("service_started"));
        Assert.assertTrue(management.getServiceInstanceState(management.getServiceInstanceId("tomcat", 1))
                .isLifecycle("service_cleaned"));
    }

}
