package org.openspaces.servicegrid;

import java.net.URI;

import com.fasterxml.jackson.annotation.JsonIgnore;

public class ImpersonatingTask extends Task {

	private final Class<? extends TaskConsumerState> impersonatedStateClass;

	public ImpersonatingTask(Class<? extends TaskConsumerState> impersonatedStateClass) {
		this.impersonatedStateClass = impersonatedStateClass;
	}

	@JsonIgnore
	public Class<? extends TaskConsumerState> getImpersonatedStateClass() {
		return impersonatedStateClass;
	}

	private URI stateId;

	public URI getStateId() {
		return stateId;
	}

	public void setStateId(URI stateId) {
		this.stateId = stateId;
	}
}
