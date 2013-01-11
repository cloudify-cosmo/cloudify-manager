package org.openspaces.servicegrid;

import java.net.URI;

public class ImpersonatingTask extends Task {

	private URI impersonatedTarget;

	public URI getImpersonatedTarget() {
		return impersonatedTarget;
	}

	public void setImpersonatedTarget(URI impersonatedTarget) {
		this.impersonatedTarget = impersonatedTarget;
	}
}
