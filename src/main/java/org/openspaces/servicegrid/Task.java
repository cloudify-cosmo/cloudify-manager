package org.openspaces.servicegrid;

import java.net.URI;
import java.util.List;

public class Task {

	private URI target;
	
	private URI impersonatedTarget;

	private URI source;

	private Long sourceTimestamp;

	private List<URI> serviceInstanceIds;

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

	public List<URI> getServiceInstanceIds() {
		return this.serviceInstanceIds;
	}

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;
	}
}
