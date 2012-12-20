package org.openspaces.servicegrid;

import static org.mockito.Mockito.mock;
import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;
import static org.testng.Assert.assertNull;

import org.openspaces.servicegrid.model.service.ServiceConfig;
import org.openspaces.servicegrid.model.service.ServiceId;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.testng.annotations.Test;

public class InstallServiceTest {

	@Test
	public void installServiceGetServiceIdTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(StateViewer.class));
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		assertNotNull(serviceId);
		assertEquals(serviceId.getServiceName(), "tomcat");
	}
	
	
	@Test
	public void installServiceGetServiceStatusTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(StateViewer.class));
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		//POST http://host/services
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		//GET http://host/services/tomcat/_status
		ServiceState state = serviceController.getServiceState(serviceId);
		assertNull(state);
	}

	@Test
	public void installServiceAndGetServiceStatusTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		StateHolder mapStateHolder = new MapServiceStateHolder();  
		StateViewer stateViewer = mapStateHolder;
		StateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator();
		MockServiceOrchestratorTaskExecutor executor = new MockServiceOrchestratorTaskExecutor(taskBrokerProvider, stateHolder, serviceOrchestrator);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer);
		
		//POST http://host/services
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		executor.stepTaskExecutor();
		//GET http://host/services/tomcat/_status
		ServiceState state = serviceController.getServiceState(serviceId);
		assertEquals(state.getId(),serviceId);
		assertEqualsServiceConfig(state.getConfig(),serviceConfig);
	}
	
	@Test(expectedExceptions = {IllegalArgumentException.class})
	public void installServiceTwiceTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		StateHolder mapStateHolder = new MapServiceStateHolder();  
		StateViewer stateViewer = mapStateHolder;
		StateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator();
		MockServiceOrchestratorTaskExecutor executor = new MockServiceOrchestratorTaskExecutor(taskBrokerProvider, stateHolder, serviceOrchestrator);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer);
		
		//POST http://host/services
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		serviceController.installService(serviceConfig);
		executor.stepTaskExecutor();
		serviceController.installService(serviceConfig);
		executor.stepTaskExecutor();
	}
	
/*
	@Test
	public void installServiceCreateNewMachineTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		StateHolder mapStateHolder = new MapServiceStateHolder();  
		StateViewer stateViewer = mapStateHolder;
		StateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator(stateHolder);
		MockBrokerPollingContainer taskProducer = new MockBrokerPollingContainer(taskBrokerProvider.getTaskBroker(serviceOrchestrator.getId()), serviceOrchestrator);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer);
		
		//POST http://host/services
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		taskProducer.step();
		taskProducer.step();
		
		//GET http://host/services/tomcat/_status
		ServiceOrchestratorState status = serviceController.getServiceStatus(serviceId);
		assertTrue(status.getLastTask() instanceof StartMachineTask);
	}
*/
	private void assertEqualsServiceConfig(
			ServiceConfig actual,
			ServiceConfig expected) {
		
		assertEquals(actual.getName(), expected.getName());
		
	}
}
