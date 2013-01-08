package org.openspaces.servicegrid.model.service;

import java.net.URI;

public class OrchestrateServiceInstanceTask extends ServiceTask {
	private URI serviceURI;

	public URI getServiceURI() {
		return serviceURI;
	}

	public void setServiceURI(URI serviceURI) {
		this.serviceURI = serviceURI;
	}
	
}
