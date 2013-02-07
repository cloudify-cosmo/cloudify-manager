package org.openspaces.servicegrid.kvstore;

import java.net.URI;
import java.util.Map;

import javax.ws.rs.core.EntityTag;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Preconditions;


public class KVStore implements KVReader, KVWriter {

	final Map<URI, EntityTagState<String>> store = Maps.newLinkedHashMap();
	
	@Override
	public String getState(URI key) {
		synchronized (store) {
		
			String state = null;
			EntityTagState<String> value = store.get(key);
			if (value != null) {
				state = value.getState();
			}
			return state;
		}
	}

	@Override
	public EntityTag getEntityTag(URI key) {
		synchronized (store) {
			
			EntityTag etag = KVEntityTag.EMPTY;
			final EntityTagState<String> value = store.get(key);
			if (value != null) {
				etag = value.getEntityTag();
			}
			return etag;
		}
	}
	
	@Override
	public EntityTag put(URI key, String state) {
		synchronized (store) {
		
			final EntityTag etag = KVEntityTag.create(state);
			final EntityTagState<String> value = new EntityTagState<String>(etag, state);
			store.put(key, value);
			return etag;
		}
	}

	public void clear() {
		synchronized (store) {
			store.clear();
		}
	}

	static class EntityTagState<T> {
	
	private final EntityTag etag;
	
	private final T state;
	
	public EntityTagState(EntityTag etag, T state) {
		Preconditions.checkNotNull(state);
		Preconditions.checkNotNull(etag);
		this.etag = etag;
		this.state = state;
	}
	
	public EntityTag getEntityTag() {
		return etag;
	}

	public T getState() {
		return state;
	}
}

}
