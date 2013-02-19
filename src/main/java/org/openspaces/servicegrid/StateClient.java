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
package org.openspaces.servicegrid;

import java.net.URI;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

import javax.ws.rs.core.MediaType;

import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.EtagPreconditionNotMetException;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.sun.jersey.api.client.Client;
import com.sun.jersey.api.client.ClientResponse;
import com.sun.jersey.api.client.ClientResponse.Status;
import com.sun.jersey.api.client.UniformInterfaceException;
import com.sun.jersey.api.client.WebResource;
import com.sun.jersey.api.client.config.ClientConfig;
import com.sun.jersey.api.client.config.DefaultClientConfig;
import com.sun.jersey.api.client.filter.LoggingFilter;

public class StateClient implements StateReader, StateWriter {
	
	private final ObjectMapper mapper;
	private final URI restUri;
	private WebResource webResource;
	private final Logger logger = Logger.getLogger(this.getClass().getName());
	private boolean enableHttpLogging = false;
	
	public StateClient(URI restUri) {
		this.restUri = restUri;
		mapper = StreamUtils.newObjectMapper();
		final ClientConfig clientConfig = new DefaultClientConfig();
		final Client client = Client.create(clientConfig);
		if (enableHttpLogging) {
			client.addFilter(new LoggingFilter(logger));
		}
		webResource = client.resource(restUri);		  
	}
	
	@Override
	public Etag put(URI id, Object state, Etag etag) {
		final String path = getPathFromId(id);
		final String json = StreamUtils.toJson(mapper,state);
		Preconditions.checkState(json.length() > 0);
		
		final int retries = 30;
		for (int i = 0 ;  ; i ++) {
			final ClientResponse response = put(path, json, etag);
			if (response.getClientResponseStatus() == ClientResponse.Status.OK) {
				return Etag.create(response);
			}
			else if ((i < (retries-1)) && response.getClientResponseStatus()== ClientResponse.Status.BAD_REQUEST) {
				//retry
				logger.warning("received error " + response.getEntity(String.class));
				continue;
			}
			else if (response.getClientResponseStatus()== ClientResponse.Status.PRECONDITION_FAILED) {
				throw new EtagPreconditionNotMetException(id, Etag.create(response), etag);
			}
			throw new UniformInterfaceException(response);
		}
	}

	private ClientResponse put(final String path, final String json, Etag etag) {
		ClientResponse response;
		if (etag.equals(Etag.empty())) {
			response = 
				webResource
					.path(path)
					.header("If-None-Match", "*")
					.header("Content-Length", json.length())
					.type(MediaType.APPLICATION_JSON)
					.put(ClientResponse.class, json);
		}
		else {
			response = 
				webResource
					.path(path)
					.header("If-Match", etag.toString())
					.header("Content-Length", json.length())
					.type(MediaType.APPLICATION_JSON)
					.put(ClientResponse.class, json);
		}
		return response;
	}

	@Override
	public <T> EtagState<T> get(URI id, Class<? extends T> clazz) {
		final String path = getPathFromId(id);
		final int maxRetries = 30;

        for(int i =0 ; ; i++) {

            try {
            	return get(path, clazz);
            } catch (Exception e) {
            	int numberOfRetriesLeft = maxRetries - i -1;
            	if (numberOfRetriesLeft > 0) {
            		logger.log(Level.INFO, "GET failed. will try " + numberOfRetriesLeft + " more time(s).", e);
            	}
            	else {
            		throw Throwables.propagate(e);    		
            	}
            }
        }
	}

	private <T> EtagState<T> get(final String path, Class<? extends T> clazz) {
		final ClientResponse response = webResource.path(path).get(ClientResponse.class);
		final Status status = response.getClientResponseStatus();
		if (status == ClientResponse.Status.OK) {
			final String json = response.getEntity(String.class);
			if (json.length() == 0) {
				Preconditions.checkState(json.length() > 0, "Retrieved empty string value for path " + path);
			}
			final Etag etag = Etag.create(response);
			final T state = StreamUtils.fromJson(mapper, json, clazz);
			return new EtagState<T>(etag, state);
		}
		else if (status == ClientResponse.Status.NOT_FOUND) {
			return null;
		}
		else {
			throw new UniformInterfaceException(response);
		}
	}
	
	private String getPathFromId(URI id) {
		Preconditions.checkArgument(id.toString().startsWith(restUri.toString()));
		return StreamUtils.fixSlash(id.toString().substring(restUri.toString().length()));
	}

	public boolean stateEquals(TaskConsumerState state1, TaskConsumerState state2) {
		return StreamUtils.elementEquals(mapper, state1, state2);
	}

	@Override
	public Iterable<URI> getElementIdsStartingWith(final URI idPrefix) {
		final String path = getPathFromId(idPrefix)+"_list";
		final String json = webResource.path(path).get(String.class);
		@SuppressWarnings("unchecked")
		final List<String> uris = StreamUtils.fromJson(mapper, json, List.class);
		return Iterables.transform(uris, new Function<String,URI>(){

			@Override
			public URI apply(String uri) {
				return StreamUtils.newURI(uri);
			}});
	}

}
