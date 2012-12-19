package org.openspaces.servicegrid;

import static org.mockito.Mockito.mock;
import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;
import static org.testng.Assert.assertNull;

import org.openspaces.servicegrid.model.ServiceConfig;
import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;
import org.testng.annotations.Test;

public class InstallServiceTest {

	@Test
	public void installServiceGetServiceIdTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(ServiceStateViewer.class));
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		assertNotNull(serviceId);
		assertEquals(serviceId.getServiceName(), "tomcat");
	}
	
	
	@Test
	public void installServiceGetServiceStatusTest() {
		
		TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, mock(ServiceStateViewer.class));
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		//POST http://host/services
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		//GET http://host/services/tomcat/_status
		ServiceState status = serviceController.getServiceStatus(serviceId);
		assertNull(status);
	}

	@Test
	public void installServiceDelegateToOrchestratorAndGetServiceStatusTest() {
		
		final TaskBrokerProvider taskBrokerProvider = new MockTaskBrokerProvider();
		ServiceStateHolder mapStateHolder = new MapServiceStateHolder();  
		ServiceStateViewer stateViewer = mapStateHolder;
		ServiceStateHolder stateHolder = mapStateHolder;
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator(stateHolder);
		MockBrokerPollingContainer taskProducer = new MockBrokerPollingContainer(taskBrokerProvider.getTaskBroker(null), serviceOrchestrator);
		
		final ServiceController serviceController = new ServiceController(taskBrokerProvider, stateViewer);
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		//POST http://host/services
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		taskProducer.step();
		//GET http://host/services/tomcat/_status
		ServiceState status = serviceController.getServiceStatus(serviceId);
		assertEqualsServiceConfig(status.getConfig(), serviceConfig);
		assertEquals(status.getId(), serviceId);
	}
	
	private void assertEqualsServiceConfig(
			ServiceConfig actual,
			ServiceConfig expected) {
		
		assertEquals(actual.getName(), expected.getName());
		
	}
}
