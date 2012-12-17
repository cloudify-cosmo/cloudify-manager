package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.ServiceConfig;
import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceStatus;
import org.openspaces.servicegrid.model.Task;
import org.testng.annotations.Test;
import static org.testng.Assert.*;
import static org.mockito.Mockito.*;

public class InstallServiceTest {

	@Test
	public void installServiceGetServiceIdTest() {
		
		final ServiceController serviceController = new ServiceController(mock(TaskBroker.class));
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		assertNotNull(serviceId);
		assertEquals(serviceId.getServiceName(), "tomcat");
	}
	
	
	@Test
	public void installServiceGetServiceStatusTest() {
		
		TaskBroker taskBroker = new MockTaskBroker();
		final ServiceController serviceController = new ServiceController(taskBroker);
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		//POST http://host/services
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		//GET http://host/services/tomcat/_status
		ServiceStatus status = serviceController.getServiceStatus(serviceId);
		assertEqualsServiceConfig(status.getConfig(), serviceConfig);
		assertEquals(status.getId(), serviceId);
		assertNull(status.getLastEvent());
	}

	@Test
	public void installServiceAndPlanGetServiceStatusTest() {
		
		final TaskBroker taskBroker = new MockTaskBroker();
		ServiceOrchestrator serviceOrchestrator = new ServiceOrchestrator();
		MockTaskProducer taskProducer = new MockTaskProducer(taskBroker, serviceOrchestrator);
		MockTaskConsumer taskConsumer = new MockTaskConsumer(taskBroker);
		
		final ServiceController serviceController = new ServiceController(taskBroker);
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setName("tomcat");
		
		
		//POST http://host/services
		final ServiceId serviceId = serviceController.installService(serviceConfig);
		
		//GET http://host/services/tomcat/_status
		ServiceStatus status = serviceController.getServiceStatus(serviceId);
		assertEqualsServiceConfig(status.getConfig(), serviceConfig);
		assertEquals(status.getId(), serviceId);
		assertNull(status.getLastEvent());
		
		taskProducer.step();
		taskConsumer.step();
	}
	
	private void assertEqualsServiceConfig(
			ServiceConfig actual,
			ServiceConfig expected) {
		
		assertEquals(actual.getName(), expected.getName());
		
	}
}
