/*******************************************************************************
 * Copyright (c) 2011 GigaSpaces Technologies Ltd. All rights reserved
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
 *******************************************************************************/
package org.openspaces.servicegrid.kvstore;

import java.net.URI;
import java.util.Map;

import javax.ws.rs.core.EntityTag;

import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;


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
		EntityTag etag = null;
		final EntityTagState<String> value = store.get(key);
		if (value != null) {
			etag = value.getEntityTag();
		}
		return Optional.fromNullable(etag);
	}
	
	@Override
	public EntityTag put(URI key, String state) {
		Preconditions.checkNotNull(key);
		Preconditions.checkNotNull(state);
		
		final EntityTag etag = KVEntityTag.create(state);
		final EntityTagState<String> value = new EntityTagState<String>(etag, state);
		store.put(key, value);
		return etag;
	
	}

	@Override
	public Iterable<URI> listKeysStartsWith(final URI keyPrefix) {
		return Iterables.filter(store.keySet(), new Predicate<URI>() {

			@Override
			public boolean apply(URI key) {
				return key.toString().startsWith(keyPrefix.toString());
			}
		});
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
