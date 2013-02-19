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

import com.google.common.base.Preconditions;


public class EtagState<T> {
	
	private final Etag etag;
	
	private final T state;
	
	public EtagState(Etag etag, T state) {
		Preconditions.checkNotNull(state);
		Preconditions.checkNotNull(etag);
		this.etag = etag;
		this.state = state;
	}
	
	public Etag getEtag() {
		return etag;
	}

	public T getState() {
		return state;
	}
}
