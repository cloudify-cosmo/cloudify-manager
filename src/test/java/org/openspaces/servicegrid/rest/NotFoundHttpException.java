package org.openspaces.servicegrid.rest;

import java.net.URL;

public class NotFoundHttpException extends HttpException {

	private static final long serialVersionUID = 1L;
	private final URL url;

	public NotFoundHttpException(URL url) {
		super(HttpError.NOT_FOUND);
		this.url = url;
	}

	@Override
	public String toString() {
		return "NotFoundHttpException [httpError=" + getHttpError() + ", url=" + url + "]";
	}


}
