package org.openspaces.servicegrid;

import static org.mockito.Mockito.mock;
import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNull;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.Map.Entry;
import java.util.UUID;

import org.openspaces.servicegrid.model.service.AggregatedServiceState;
import org.openspaces.servicegrid.model.service.ServiceConfig;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceInstanceState.Progress;
import org.testng.annotations.Test;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;

public class InstallServiceTest {

	private final URL serviceOrchestratorId;
	private final URL managementExecutorId;

	InstallServiceTest() {
		try {
			managementExecutorId = new URL("http://localhost/executors/" + UUID.randomUUID());
			serviceOrchestratorId = new URL("http://localhost/executors/" + UUID.randomUUID());
		} catch (MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}
	
	@Test
	public void installServiceGetServiceIdTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(StateViewer.class), serviceOrchestratorId);
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");

		//POST http://host/services
		final URL tomcatServiceId = serviceController.installService(serviceConfig);
		assertEquals(tomcatServiceId, serviceOrchestratorId);
	}
	
	
	@Test
	public void installServiceGetServiceStatusTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(StateViewer.class), serviceOrchestratorId);
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		//POST http://host/services
		final URL tomcatServiceId = serviceController.installService(serviceConfig);
		//TODO: Should HTTP return 200 or 201 or 202 ? -> Future<URL> ?
		
		//GET http://host/services/12345
		AggregatedServiceState state = serviceController.getServiceState(tomcatServiceId);
		assertNull(state);
	}

	@Test
	public void installServiceStepExecutorAndGetServiceStatusTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		StateHolder mapStateHolder = new MapServiceStateHolder();  
		StateViewer stateViewer = mapStateHolder;
		StateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator(managementExecutorId );
		MockOrchestratorTaskPolling executor = new MockOrchestratorTaskPolling(serviceOrchestratorId, taskBrokerProvider, stateHolder, serviceOrchestrator);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer, serviceOrchestratorId);
		
		//POST http://host/services
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		final URL tomcatServiceId = serviceController.installService(serviceConfig);
		
		executor.stepTaskExecutor();
		//GET http://host/services/tomcat/_aggregated
		AggregatedServiceState serviceState = serviceController.getServiceState(tomcatServiceId);
		assertEqualsServiceConfig(serviceState.getConfig(),serviceConfig);
	}
			
	@Test
	public void installServiceCreateNewMachineTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		StateHolder mapStateHolder = new MapServiceStateHolder();  
		StateViewer stateViewer = mapStateHolder;
		StateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator(managementExecutorId );
		MockOrchestratorTaskPolling orchestratorPolling = new MockOrchestratorTaskPolling(serviceOrchestratorId, taskBrokerProvider, stateHolder, serviceOrchestrator);
		
		TaskExecutor<?> cloudExecutor = new CloudMachineTaskExecutor();
		MockTaskPolling executorPolling = new MockTaskPolling(managementExecutorId, taskBrokerProvider, stateHolder, cloudExecutor);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer, serviceOrchestratorId);
		
		//POST http://host/services
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		final URL tomcatServiceId = serviceController.installService(serviceConfig);
		
		orchestratorPolling.stepTaskExecutor();
		orchestratorPolling.stepTaskOrchestrator();
		executorPolling.stepTaskExecutor();
		
		//GET http://host/services/tomcat
		AggregatedServiceState serviceState = serviceController.getServiceState(tomcatServiceId);
		assertEqualsServiceConfig(serviceState.getConfig(),serviceConfig);
		
		Entry<URL, ServiceInstanceState> instance = Iterables.getOnlyElement(serviceState.getInstances().entrySet());
		assertEquals(instance.getValue().getProgress(), Progress.STARTING_MACHINE);
	}

	private void assertEqualsServiceConfig(
			ServiceConfig actual,
			ServiceConfig expected) {
		
		assertEquals(actual.getName(), expected.getName());
		
	}
}
