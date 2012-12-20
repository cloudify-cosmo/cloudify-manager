package org.openspaces.servicegrid.model.tasks;

import java.net.URL;

public class Task {

	private URL target;
	
	//@JsonIgnore
	private URL id;

	public void setTarget(URL target) {
		this.target = target;
	}
	
	public URL getTarget() {
		return target;
	}

	public URL getId() {
		return id;
	}

	public void setId(URL id) {
		this.id = id;
	}
}
