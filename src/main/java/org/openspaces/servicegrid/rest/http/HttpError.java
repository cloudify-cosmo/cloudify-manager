package org.openspaces.servicegrid.rest.http;

public enum HttpError {

	BAD_REQUEST(400), 
	NOT_FOUND(404),
	HTTP_CONFLICT(409);
	
	private int errorCode;

	HttpError(int errorCode) {
		this.errorCode = errorCode;
	}

	public int getErrorCode() {
		return errorCode;
	}
	
}
