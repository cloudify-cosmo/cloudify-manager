package org.openspaces.servicegrid.state;

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
