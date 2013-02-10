package org.openspaces.servicegrid.state;

import java.net.URI;

public class EtagPreconditionNotMetException extends RuntimeException {

	private static final long serialVersionUID = 1L;
	private Etag responseEtag;
	private Etag requestEtag;

	public EtagPreconditionNotMetException(URI id, Etag responseEtag, Etag requestEtag) {
		super(String.format("Etag mismatch for %s. Request Etag %s. Response Etag %s",id, requestEtag, responseEtag));
		this.responseEtag = responseEtag;
		this.requestEtag = requestEtag;
	}

	public Etag getResponseEtag() {
		return responseEtag;
	}

	public Etag getRequestEtag() {
		return requestEtag;
	}
}
