package org.openspaces.servicegrid.model.tasks;

import java.net.URI;

public class Task {

	private URI target;
	
	private URI impersonatedTarget;

	private URI source;

	private Long sourceTimestamp;

	public URI getSource() {
		return source;
	}

	public URI getImpersonatedTarget() {
		return impersonatedTarget;
	}

	public void setTarget(URI target) {
		this.target = target;
	}
	
	public URI getTarget() {
		return target;
	}

	public void setImpersonatedTarget(URI impersonatedTarget) {
		this.impersonatedTarget = impersonatedTarget;
	}
	
	public void setSource(URI source) {
		this.source = source;
	}

	public Long getSourceTimestamp() {
		return sourceTimestamp;
	}

	public void setSourceTimestamp(Long sourceTimestamp) {
		this.sourceTimestamp = sourceTimestamp;
	}
}
