package org.openspaces.servicegrid;

import java.net.URI;

public class ImpersonatingTask extends Task {

	private URI stateId;

	public URI getStateId() {
		return stateId;
	}

	public void setStateId(URI stateId) {
		this.stateId = stateId;
	}
}
