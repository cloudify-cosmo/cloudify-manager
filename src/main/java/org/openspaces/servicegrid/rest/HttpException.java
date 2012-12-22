package org.openspaces.servicegrid.rest;

public class HttpException extends RuntimeException {

	private static final long serialVersionUID = 1L;
	private final HttpError httpError;

	public HttpException(HttpError httpError) {
		this.httpError = httpError;
	}

	public HttpError getHttpError() {
		return httpError;
	}

	@Override
	public String toString() {
		return "RestfulException [httpError=" + httpError + "]";
	}
}
