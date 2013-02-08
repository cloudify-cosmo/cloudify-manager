package org.openspaces.servicegrid.kvstore;

import java.net.URI;
import java.util.Map;

import javax.ws.rs.core.EntityTag;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;


public class KVStore implements KVReader, KVWriter {

	final Map<URI, EntityTagState<String>> store = Maps.newLinkedHashMap();
	
	@Override
	public Optional<EntityTagState<String>> getState(URI key) {
		synchronized (store) {
		
			EntityTagState<String> value = store.get(key);
			return Optional.fromNullable(value);
		}
	}

	@Override
	public Optional<EntityTag> getEntityTag(URI key) {
		synchronized (store) {
			EntityTag etag = null;
			final EntityTagState<String> value = store.get(key);
			if (value != null) {
				etag = value.getEntityTag();
			}
			return Optional.fromNullable(etag);
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

	@Override
	public Iterable<URI> listKeysStartsWith(final URI keyPrefix) {
		synchronized (store) {
			return Iterables.filter(store.keySet(), new Predicate<URI>() {

				@Override
				public boolean apply(URI key) {
					return key.toString().startsWith(keyPrefix.toString());
				}
			});
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
