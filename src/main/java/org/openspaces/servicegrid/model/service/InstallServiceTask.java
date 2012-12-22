package org.openspaces.servicegrid.model.service;

import java.net.URL;


public class InstallServiceTask extends ServiceTask {
	
	private URL downloadUrl;

	public URL getDownloadUrl() {
		return downloadUrl;
	}

	public void setDownloadUrl(URL downloadUrl) {
		this.downloadUrl = downloadUrl;
	}
}
