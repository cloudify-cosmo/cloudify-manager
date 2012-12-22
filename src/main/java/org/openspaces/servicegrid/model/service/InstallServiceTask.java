package org.openspaces.servicegrid.model.service;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.ServiceTask;

public class InstallServiceTask extends ServiceTask {
	
	private URL downloadUrl;

	public URL getDownloadUrl() {
		return downloadUrl;
	}

	public void setDownloadUrl(URL downloadUrl) {
		this.downloadUrl = downloadUrl;
	}
}
