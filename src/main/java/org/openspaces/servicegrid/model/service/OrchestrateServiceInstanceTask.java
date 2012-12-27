package org.openspaces.servicegrid.model.service;

import java.net.URL;

public class OrchestrateServiceInstanceTask extends ServiceTask {
	private URL serviceUrl;

	public URL getServiceUrl() {
		return serviceUrl;
	}

	public void setServiceUrl(URL serviceUrl) {
		this.serviceUrl = serviceUrl;
	}
	
}
