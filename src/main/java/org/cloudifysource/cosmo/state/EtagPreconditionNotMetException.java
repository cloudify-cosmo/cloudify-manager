/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.cloudifysource.cosmo.state;

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
